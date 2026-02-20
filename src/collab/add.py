"""
Add a new collaborator: create shared GitHub repo, init it, add as submodule.

Usage:
  uv run collab-add alex --label for-alex --github-user alex-gh
  uv run collab-add alex --label for-alex --pat
  uv run collab-add alex --label for-alex --public --github-user alex-gh
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from . import Collaborator, load_collaborators, save_collaborators

load_dotenv()

SHARED_DIR = Path("shared")
VOICE_FILE = Path("voice.md")
TEMPLATES_DIR = Path(__file__).parent / "templates"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, printing it first. Exits on failure."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        sys.exit(1)
    return result


def _generate_readme_md() -> str:
    return """# Shared Correspondence with Brian

This repo contains email threads Brian has shared with you and a place for you
to draft replies on his behalf.

## Quick start

```sh
git clone <this-repo-url>
cd correspondence-shared-alex
```

### 1. Read conversations

Synced threads are in `conversations/`. Pull to get the latest:

```sh
git pull
```

### 2. Find threads that need a reply

```sh
uvx corrkit find-unanswered
```

### 3. Draft a reply

Create a file in `drafts/` named `YYYY-MM-DD-slug.md`:

```markdown
# Subject

**To**: recipient@example.com
**Status**: review
**Author**: alex

---

Your reply here.
```

Set **Status** to `review` when it's ready for Brian to look at.

### 4. Validate and push

```sh
uvx corrkit validate-draft drafts/your-draft.md
git add drafts/
git commit -m "Draft reply to ..."
git push
```

Brian will review your draft, and if approved, send it from his email account.

## Reference

See `AGENTS.md` for the full draft format (CC, In-Reply-To, Account, From),
conversation format, status flow, and voice guidelines.
"""


def _generate_agents_md(name: str) -> str:
    return f"""# Shared Correspondence with Brian

## Workflow

1. `git pull` to get the latest synced conversations
2. Read threads in `conversations/` for context
3. Draft replies in `drafts/`
4. `git add`, `git commit`, and `git push` when done

## Conversation format

Synced conversations live in `conversations/{{label}}/`. Each file is one thread:

```markdown
# Subject Line

**Label**: label-name
**Thread ID**: thread-id
**Last updated**: 2026-02-19

---

## Sender Name <sender@example.com> — Mon, 10 Feb 2025 10:00:00 +0000

Message body text.

---

## Another Sender — Mon, 10 Feb 2025 11:00:00 +0000

Reply body text.
```

## Finding unanswered threads

Run the helper command to find threads awaiting a reply:

```sh
uvx corrkit find-unanswered
uvx corrkit find-unanswered --from "Brian"
```

## Drafting a reply

Create a file in `drafts/` named `YYYY-MM-DD-slug.md`:

```markdown
# Subject

**To**: recipient@example.com
**CC**: (optional)
**Status**: review
**Author**: {name}
**Account**: (optional -- account name for sending)
**From**: (optional -- email address for sending)
**In-Reply-To**: (optional -- message ID from thread)

---

Body text here.
```

### Required fields
- `# Subject` heading
- `**To**`: recipient email
- `**Status**`: set to `review` when ready for Brian
- `**Author**`: your name (`{name}`)
- `---` separator before the body

### Replying to an existing thread
Set `**In-Reply-To**` to a message ID from the conversation thread. Message IDs
are not shown in the markdown files -- ask Brian for the ID or leave it blank
and note which thread you're replying to in the body.

### Validating a draft

```sh
uvx corrkit validate-draft drafts/2026-02-19-example.md
```

### Status flow

`draft` -> `review` -> `approved` -> `sent`

- **draft**: work in progress (not ready for Brian)
- **review**: ready for Brian to review
- **approved**: Brian approved, ready to send
- **sent**: email has been sent (only Brian sets this)

## Voice guidelines

See `voice.md` for Brian's writing voice. Match this style when drafting on his behalf.

## What you can do

- Read conversations
- Create and edit drafts
- Run `uvx corrkit find-unanswered` and `uvx corrkit validate-draft`
- Push changes to this repo

## What only Brian can do

- Sync new emails into this repo
- Send emails (requires email credentials)
- Change draft Status to `sent`
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a new collaborator")
    parser.add_argument("name", help="Collaborator name (used for directory & repo)")
    parser.add_argument(
        "--label",
        action="append",
        required=True,
        help="Gmail label(s) to share (repeatable)",
    )
    parser.add_argument("--github-user", help="GitHub username to add as collaborator")
    parser.add_argument(
        "--pat",
        action="store_true",
        help="Use PAT-based access instead of GitHub collaborator invite",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create the shared repo as public (default: private)",
    )
    parser.add_argument(
        "--account",
        default="",
        help="Bind collaborator labels to a specific account name",
    )
    parser.add_argument(
        "--org",
        default="btakita",
        help="GitHub org/user for the shared repo (default: btakita)",
    )
    args = parser.parse_args()

    name: str = args.name
    labels: list[str] = args.label
    repo_name = f"correspondence-shared-{name}"
    repo_full = f"{args.org}/{repo_name}"

    # Check not already configured
    collabs = load_collaborators()
    if name in collabs:
        print(f"Collaborator '{name}' already exists in collaborators.toml")
        sys.exit(1)

    submodule_path = SHARED_DIR / name
    if submodule_path.exists():
        print(f"Directory shared/{name} already exists")
        sys.exit(1)

    # 1. Create GitHub repo
    visibility = "--public" if args.public else "--private"
    print(f"Creating GitHub repo: {repo_full} ({visibility.lstrip('-')})")
    _run(["gh", "repo", "create", repo_full, visibility, "--confirm"])

    # 2. Add collaborator if --github-user
    if args.github_user:
        print(f"Adding {args.github_user} as collaborator on {repo_full}")
        _run(
            [
                "gh",
                "api",
                f"repos/{repo_full}/collaborators/{args.github_user}",
                "-X",
                "PUT",
                "--silent",
            ]
        )
    elif args.pat:
        print()
        print("PAT access mode selected. The collaborator should:")
        print("  1. Go to https://github.com/settings/personal-access-tokens/new")
        print(f"  2. Create a fine-grained PAT scoped to: {repo_full}")
        print("  3. Grant 'Contents' read/write permission")
        print(f"  4. Use the PAT to clone: https://github.com/{repo_full}.git")
        print()

    # 3. Initialize the shared repo
    print("Initializing shared repo contents...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _run(["gh", "repo", "clone", repo_full, str(tmp)])

        # AGENTS.md + CLAUDE.md symlink + README.md
        (tmp / "AGENTS.md").write_text(_generate_agents_md(name), encoding="utf-8")
        os.symlink("AGENTS.md", tmp / "CLAUDE.md")
        (tmp / "README.md").write_text(_generate_readme_md(), encoding="utf-8")

        # .gitignore
        (tmp / ".gitignore").write_text(
            "AGENTS.local.md\nCLAUDE.local.md\n__pycache__/\n",
            encoding="utf-8",
        )

        # voice.md
        if VOICE_FILE.exists():
            shutil.copy2(VOICE_FILE, tmp / "voice.md")

        # directories
        (tmp / "conversations").mkdir(exist_ok=True)
        (tmp / "conversations" / ".gitkeep").touch()
        (tmp / "drafts").mkdir(exist_ok=True)
        (tmp / "drafts" / ".gitkeep").touch()

        # GitHub Actions workflow
        (tmp / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        notify_src = TEMPLATES_DIR / "notify.yml"
        if notify_src.exists():
            shutil.copy2(notify_src, tmp / ".github" / "workflows" / "notify.yml")

        # commit and push
        _run(["git", "-C", str(tmp), "add", "-A"])
        _run(
            [
                "git",
                "-C",
                str(tmp),
                "commit",
                "-m",
                f"Initialize shared correspondence repo for {name}",
            ]
        )
        _run(["git", "-C", str(tmp), "push"])

    # 4. Add as git submodule
    SHARED_DIR.mkdir(exist_ok=True)
    repo_url = f"git@github.com:{repo_full}.git"
    print(f"Adding submodule: shared/{name} -> {repo_url}")
    _run(["git", "submodule", "add", repo_url, f"shared/{name}"])

    # 5. Update collaborators.toml
    collabs[name] = Collaborator(
        labels=labels,
        repo=repo_full,
        github_user=args.github_user or "",
        account=args.account,
    )
    save_collaborators(collabs)
    print("Updated collaborators.toml")

    # 6. Remind about GMAIL_SYNC_LABELS
    print()
    print("Done! Next steps:")
    for label in labels:
        print(f"  - Ensure '{label}' is in GMAIL_SYNC_LABELS in .env")
    print("  - Run: uv run sync-gmail --full")
    print(f"  - Run: uv run collab-sync {name}")


if __name__ == "__main__":
    main()
