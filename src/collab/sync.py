"""
Sync shared collaborator submodules: pull changes, push updates.

Usage:
  corrkit for sync              # Sync all collaborators
  corrkit for sync alex-gh      # Sync one collaborator
  corrkit for sync --status     # Quick status check (no push/pull)
  corrkit for status            # Alias for --status
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import resolve

from . import collab_dir, load_collaborators

TEMPLATES_DIR = Path(__file__).parent / "templates"

_TEMPLATE_WORKFLOW = "notify.yml"


def _run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if check and result.returncode != 0:
        print(f"  FAILED: {' '.join(cmd)}")
        print(f"  {result.stderr.strip()}")
    return result


def _submodule_status(name: str, sub_path: Path) -> None:
    """Print incoming/outgoing commit counts for a submodule."""
    _run(["git", "-C", str(sub_path), "fetch"], check=False)

    # Incoming (remote ahead of local)
    incoming = _run(
        ["git", "-C", str(sub_path), "rev-list", "--count", "HEAD..@{u}"],
        check=False,
    )
    # Outgoing (local ahead of remote)
    outgoing = _run(
        ["git", "-C", str(sub_path), "rev-list", "--count", "@{u}..HEAD"],
        check=False,
    )

    inc = incoming.stdout.strip() if incoming.returncode == 0 else "?"
    out = outgoing.stdout.strip() if outgoing.returncode == 0 else "?"

    if inc == "0" and out == "0":
        print(f"  {name}: up to date")
    else:
        parts = []
        if inc != "0":
            parts.append(f"{inc} incoming")
        if out != "0":
            parts.append(f"{out} outgoing")
        print(f"  {name}: {', '.join(parts)}")


def _sync_one(name: str) -> None:
    """Full sync for one collaborator submodule."""
    collabs = load_collaborators()
    collab = collabs.get(name)
    if collab is None:
        print(f"  {name}: not found in collaborators.toml -- skipping")
        return

    sub_path = collab_dir(collab)
    if not sub_path.exists():
        print(f"  {name}: submodule not found at {sub_path} -- skipping")
        return

    print(f"Syncing {name}...")

    # Pull collaborator's changes
    result = _run(["git", "-C", str(sub_path), "pull", "--rebase"], check=False)
    if result.returncode == 0:
        pulled = result.stdout.strip()
        if "Already up to date" not in pulled:
            print("  Pulled changes")
    else:
        print("  Pull failed -- continuing with push")

    # Copy voice.md if root copy is newer
    voice_file = resolve.voice_md()
    sub_voice = sub_path / "voice.md"
    if voice_file.exists():
        root_newer = voice_file.stat().st_mtime > sub_voice.stat().st_mtime
        if not sub_voice.exists() or root_newer:
            shutil.copy2(voice_file, sub_voice)
            print("  Updated voice.md")

    # Sync GitHub Actions workflow
    workflow_src = TEMPLATES_DIR / _TEMPLATE_WORKFLOW
    if workflow_src.exists():
        workflow_dir = sub_path / ".github" / "workflows"
        workflow_dst = workflow_dir / _TEMPLATE_WORKFLOW
        if (
            not workflow_dst.exists()
            or workflow_src.stat().st_mtime > workflow_dst.stat().st_mtime
        ):
            workflow_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workflow_src, workflow_dst)
            print(f"  Updated .github/workflows/{_TEMPLATE_WORKFLOW}")

    # Stage, commit, push any local changes
    _run(["git", "-C", str(sub_path), "add", "-A"], check=False)

    # Check if there's anything to commit
    status = _run(["git", "-C", str(sub_path), "status", "--porcelain"], check=False)
    if status.stdout.strip():
        _run(
            ["git", "-C", str(sub_path), "commit", "-m", "Sync shared conversations"],
            check=False,
        )
        result = _run(["git", "-C", str(sub_path), "push"], check=False)
        if result.returncode == 0:
            print("  Pushed changes")
        else:
            print(f"  Push failed: {result.stderr.strip()}")
    else:
        print("  No local changes to push")

    # Update submodule ref in parent
    _run(["git", "add", str(sub_path)], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync collaborator submodules")
    parser.add_argument(
        "name", nargs="?", help="Collaborator GitHub username (default: all)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Just show incoming/outgoing counts, don't sync",
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

    if args.status:
        print("Collaborator status:")
        for name in names:
            sub_path = collab_dir(collabs[name])
            if sub_path.exists():
                _submodule_status(name, sub_path)
            else:
                print(f"  {name}: submodule not found")
    else:
        for name in names:
            _sync_one(name)


def status_main() -> None:
    """Entry point for 'corrkit for status' (shortcut for 'for sync --status')."""
    sys.argv = [sys.argv[0], "--status", *sys.argv[1:]]
    main()


if __name__ == "__main__":
    main()
