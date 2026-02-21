"""
Add a new collaborator: create shared GitHub repo, init it, add as submodule.

Usage:
  corrkit for add alex-gh --label for-alex --name "Alex"
  corrkit for add bot-agent --label for-bot --pat
  corrkit for add alex-gh --label for-alex --public --name "Alex"
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from . import Collaborator, collab_dir, load_collaborators, save_collaborators

load_dotenv()

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


def _generate_readme_md(name: str, owner_name: str) -> str:
    return f"""# Shared Correspondence with {owner_name}

This repo contains email threads {owner_name} has shared with you and a place for you
to draft replies on his behalf.

## Quick start

```sh
git clone <this-repo-url>
cd <repo-name>
```

### 1. Read conversations

Synced threads are in `conversations/`. Pull to get the latest:

```sh
git pull
```

### 2. Find threads that need a reply

```sh
uvx corrkit by find-unanswered
```

### 3. Draft a reply

Create a file in `drafts/` named `YYYY-MM-DD-slug.md`:

```markdown
# Subject

**To**: recipient@example.com
**Status**: review
**Author**: {name}

---

Your reply here.
```

Set **Status** to `review` when it's ready for {owner_name} to look at.

### 4. Validate and push

```sh
uvx corrkit by validate-draft drafts/your-draft.md
git add drafts/
git commit -m "Draft reply to ..."
git push
```

{owner_name} will review your draft, and if approved, send it from his email account.

## Reference

See `AGENTS.md` for the full draft format (CC, In-Reply-To, Account, From),
conversation format, status flow, and voice guidelines.
"""


def _generate_agents_md(name: str, owner_name: str = "Brian") -> str:
    return f"""# Shared Correspondence with {owner_name}

## Workflow

1. `git pull` to get the latest synced conversations
2. Read threads in `conversations/` for context
3. Draft replies in `drafts/`
4. `git add`, `git commit`, and `git push` when done

## Conversation format

Synced conversations live in `conversations/`. Each file is one thread:

```markdown
# Subject Line

**Labels**: label-name, other-label
**Accounts**: personal
**Thread ID**: thread-id
**Last updated**: Mon, 10 Feb 2025 11:00:00 +0000

---

## Sender Name <sender@example.com> \u2014 Mon, 10 Feb 2025 10:00:00 +0000

Message body text.

---

## Another Sender \u2014 Mon, 10 Feb 2025 11:00:00 +0000

Reply body text.
```

## Finding unanswered threads

Run the helper command to find threads awaiting a reply:

```sh
uvx corrkit by find-unanswered
uvx corrkit by find-unanswered --from "{owner_name}"
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
- `**Status**`: set to `review` when ready for {owner_name}
- `**Author**`: your name (`{name}`)
- `---` separator before the body

### Replying to an existing thread
Set `**In-Reply-To**` to a message ID from the conversation thread. Message IDs
are not shown in the markdown files -- ask {owner_name} for the ID or leave it blank
and note which thread you're replying to in the body.

### Validating a draft

```sh
uvx corrkit by validate-draft drafts/2026-02-19-example.md
```

### Status flow

`draft` -> `review` -> `approved` -> `sent`

- **draft**: work in progress (not ready for {owner_name})
- **review**: ready for {owner_name} to review
- **approved**: {owner_name} approved, ready to send
- **sent**: email has been sent (only {owner_name} sets this)

## Voice guidelines

See `voice.md` for {owner_name}'s writing voice. Match this style when drafting
on his behalf.

## What you can do

- Read conversations
- Create and edit drafts
- Run `uvx corrkit by find-unanswered` and `uvx corrkit by validate-draft`
- Push changes to this repo

## What only {owner_name} can do

- Sync new emails into this repo
- Send emails (requires email credentials)
- Change draft Status to `sent`
"""


def main() -> None:
    from accounts import load_owner

    parser = argparse.ArgumentParser(description="Add a new collaborator")
    parser.add_argument("github_user", help="Collaborator's GitHub username")
    parser.add_argument(
        "--label",
        action="append",
        required=True,
        help="Gmail label(s) to share (repeatable)",
    )
    parser.add_argument("--name", default="", help="Display name for the collaborator")
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
        default="",
        help="GitHub org/user for the shared repo (default: owner's github_user)",
    )
    args = parser.parse_args()

    owner = load_owner()
    gh_user: str = args.github_user
    gh_user_lower = gh_user.lower()
    labels: list[str] = args.label
    org = args.org or owner.github_user
    owner_name = owner.name or owner.github_user
    repo_name = f"to-{gh_user_lower}"
    repo_full = f"{org}/{repo_name}"

    # Check not already configured
    collabs = load_collaborators()
    if gh_user in collabs:
        print(f"Collaborator '{gh_user}' already exists in collaborators.toml")
        sys.exit(1)

    collab_obj = Collaborator(
        labels=labels,
        github_user=gh_user,
        name=args.name,
        repo=repo_full,
        account=args.account,
    )
    submodule_path = collab_dir(collab_obj)
    if submodule_path.exists():
        print(f"Directory {submodule_path} already exists")
        sys.exit(1)

    # 1. Create GitHub repo
    visibility = "--public" if args.public else "--private"
    print(f"Creating GitHub repo: {repo_full} ({visibility.lstrip('-')})")
    _run(["gh", "repo", "create", repo_full, visibility, "--confirm"])

    # 2. Add collaborator if not --pat
    if not args.pat:
        print(f"Adding {gh_user} as collaborator on {repo_full}")
        _run(
            [
                "gh",
                "api",
                f"repos/{repo_full}/collaborators/{gh_user}",
                "-X",
                "PUT",
                "--silent",
            ]
        )
    else:
        print()
        print("PAT access mode selected. The collaborator should:")
        print("  1. Go to https://github.com/settings/personal-access-tokens/new")
        print(f"  2. Create a fine-grained PAT scoped to: {repo_full}")
        print("  3. Grant 'Contents' read/write permission")
        print(f"  4. Use the PAT to clone: https://github.com/{repo_full}.git")
        print()

    # 3. Initialize the shared repo
    display = args.name or gh_user
    print("Initializing shared repo contents...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _run(["gh", "repo", "clone", repo_full, str(tmp)])

        # AGENTS.md + CLAUDE.md symlink + README.md
        (tmp / "AGENTS.md").write_text(
            _generate_agents_md(display, owner_name), encoding="utf-8"
        )
        os.symlink("AGENTS.md", tmp / "CLAUDE.md")
        (tmp / "README.md").write_text(
            _generate_readme_md(display, owner_name), encoding="utf-8"
        )

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
                f"Initialize shared correspondence repo for {display}",
            ]
        )
        _run(["git", "-C", str(tmp), "push"])

    # 4. Add as git submodule
    repo_url = f"git@github.com:{repo_full}.git"
    sub_path = str(submodule_path)
    print(f"Adding submodule: {sub_path} -> {repo_url}")
    _run(["git", "submodule", "add", repo_url, sub_path])

    # 5. Update collaborators.toml
    collabs[gh_user] = collab_obj
    save_collaborators(collabs)
    print("Updated collaborators.toml")

    # 6. Remind about label sync
    print()
    print("Done! Next steps:")
    for label in labels:
        print(f"  - Ensure '{label}' is in your account's labels in accounts.toml")
    print("  - Run: corrkit sync --full")
    print(f"  - Run: corrkit for sync {gh_user}")


if __name__ == "__main__":
    main()
