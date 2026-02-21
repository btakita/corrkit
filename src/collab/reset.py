"""
Regenerate template files in shared collaborator repos.

Pulls the latest from the remote (rebase), rewrites AGENTS.md, README.md,
CLAUDE.md symlink, .gitignore, voice.md, and .github/workflows/notify.yml
to match the current templates, then commits and pushes.

Usage:
  corrkit for reset alex-gh         # Reset one collaborator
  corrkit for reset                 # Reset all collaborators
  corrkit for reset --no-sync       # Regenerate without pull/push
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import collab_dir, load_collaborators
from .add import _generate_agents_md, _generate_readme_md

VOICE_FILE = Path("voice.md")
TEMPLATES_DIR = Path(__file__).parent / "templates"

_TEMPLATE_WORKFLOW = "notify.yml"


def _run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if check and result.returncode != 0:
        print(f"  FAILED: {' '.join(cmd)}")
        print(f"  {result.stderr.strip()}")
    return result


def _regenerate(name: str, display_name: str, owner_name: str, sub_path: Path) -> None:
    """Regenerate template files for one collaborator."""
    # AGENTS.md
    (sub_path / "AGENTS.md").write_text(
        _generate_agents_md(display_name, owner_name), encoding="utf-8"
    )
    print("  Updated AGENTS.md")

    # CLAUDE.md symlink
    claude_md = sub_path / "CLAUDE.md"
    if claude_md.exists() or claude_md.is_symlink():
        claude_md.unlink()
    os.symlink("AGENTS.md", claude_md)
    print("  Updated CLAUDE.md -> AGENTS.md")

    # README.md
    (sub_path / "README.md").write_text(
        _generate_readme_md(display_name, owner_name), encoding="utf-8"
    )
    print("  Updated README.md")

    # .gitignore
    (sub_path / ".gitignore").write_text(
        "AGENTS.local.md\nCLAUDE.local.md\n__pycache__/\n", encoding="utf-8"
    )
    print("  Updated .gitignore")

    # voice.md
    if VOICE_FILE.exists():
        shutil.copy2(VOICE_FILE, sub_path / "voice.md")
        print("  Updated voice.md")

    # .github/workflows/notify.yml
    workflow_src = TEMPLATES_DIR / _TEMPLATE_WORKFLOW
    if workflow_src.exists():
        workflow_dir = sub_path / ".github" / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workflow_src, workflow_dir / _TEMPLATE_WORKFLOW)
        print(f"  Updated .github/workflows/{_TEMPLATE_WORKFLOW}")


def _reset_one(name: str, collab, owner_name: str, *, sync: bool = True) -> None:
    """Pull, regenerate templates, commit, and push for one collaborator."""
    sub_path = collab_dir(collab)
    if not sub_path.exists():
        print(f"  {name}: submodule not found at {sub_path} -- skipping")
        return

    print(f"Resetting {name}...")

    # 1. Pull latest (rebase to keep collaborator changes)
    if sync:
        result = _run(["git", "-C", str(sub_path), "pull", "--rebase"], check=False)
        if result.returncode == 0:
            pulled = result.stdout.strip()
            if "Already up to date" not in pulled:
                print("  Pulled changes")
        else:
            print("  Pull failed -- continuing with reset")

    # 2. Regenerate template files
    display_name = collab.name or name
    _regenerate(name, display_name, owner_name, sub_path)

    if not sync:
        return

    # 3. Stage, commit, push
    _run(["git", "-C", str(sub_path), "add", "-A"], check=False)

    status = _run(["git", "-C", str(sub_path), "status", "--porcelain"], check=False)
    if status.stdout.strip():
        _run(
            [
                "git",
                "-C",
                str(sub_path),
                "commit",
                "-m",
                "Reset template files to current version",
            ],
            check=False,
        )
        result = _run(["git", "-C", str(sub_path), "push"], check=False)
        if result.returncode == 0:
            print("  Pushed changes")
        else:
            print(f"  Push failed: {result.stderr.strip()}")
    else:
        print("  Templates already up to date")

    # 4. Update submodule ref in parent
    _run(["git", "add", str(sub_path)], check=False)


def main() -> None:
    from accounts import load_owner

    parser = argparse.ArgumentParser(
        description="Regenerate template files in shared collaborator repos"
    )
    parser.add_argument(
        "name", nargs="?", help="Collaborator GitHub username (default: all)"
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Regenerate files without pulling/pushing",
    )
    args = parser.parse_args()

    collabs = load_collaborators()
    if not collabs:
        print("No collaborators configured in collaborators.toml")
        return

    names = [args.name] if args.name else list(collabs.keys())
    for name in names:
        if name not in collabs:
            print(f"Unknown collaborator: {name}")
            sys.exit(1)

    owner = load_owner()
    owner_name = owner.name or owner.github_user

    for name in names:
        _reset_one(name, collabs[name], owner_name, sync=not args.no_sync)


if __name__ == "__main__":
    main()
