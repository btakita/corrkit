"""
Rename a collaborator's local directory and config entry.

Usage:
  corrkit for rename old-name new-name
"""

import argparse
import subprocess
import sys
from pathlib import Path

import resolve

from . import load_collaborators, save_collaborators


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        sys.exit(1)
    return result


def _find_collab_dir(name: str) -> Path | None:
    """Find the collaborator directory (for/ or by/ inside correspondence)."""
    dd = resolve.data_dir()
    for prefix in [dd / "for", dd / "by"]:
        candidate = prefix / name.lower()
        if candidate.exists():
            return candidate
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Rename a collaborator")
    parser.add_argument("old_name", help="Current collaborator name (TOML key)")
    parser.add_argument("new_name", help="New collaborator name")
    parser.add_argument(
        "--rename-repo",
        action="store_true",
        help="Also rename the GitHub repo to match the new name",
    )
    args = parser.parse_args()

    old_name: str = args.old_name
    new_name: str = args.new_name

    collabs = load_collaborators()

    if old_name not in collabs:
        print(f"Collaborator '{old_name}' not found in collaborators.toml")
        sys.exit(1)

    if new_name in collabs:
        print(f"Collaborator '{new_name}' already exists in collaborators.toml")
        sys.exit(1)

    collab = collabs[old_name]

    # 1. Move directory via git mv (if it exists)
    old_dir = _find_collab_dir(old_name)
    if old_dir is not None:
        new_dir = old_dir.parent / new_name.lower()
        print(f"Moving {old_dir} → {new_dir}")
        _run(["git", "mv", str(old_dir), str(new_dir)])
    else:
        print(f"Directory for '{old_name}' not found on disk — skipping git mv")

    # 2. Optionally rename the GitHub repo
    if args.rename_repo and collab.repo:
        try:
            from accounts import load_owner

            owner_gh = load_owner().github_user
        except (SystemExit, ImportError):
            owner_gh = ""
        new_repo_name = f"to-{new_name.lower()}"
        print(f"Renaming GitHub repo {collab.repo} → {new_repo_name}")
        _run(["gh", "repo", "rename", new_repo_name, "-R", collab.repo, "--yes"])
        # Update repo field to reflect the new name
        new_repo = f"{owner_gh}/{new_repo_name}" if owner_gh else new_repo_name
    else:
        new_repo = collab.repo

    # 3. Update collaborators.toml
    import msgspec.structs

    updated = msgspec.structs.replace(collab, github_user=new_name, repo=new_repo)
    del collabs[old_name]
    collabs[new_name] = updated
    save_collaborators(collabs)
    print(f"Renamed '{old_name}' → '{new_name}' in collaborators.toml")

    print(f"Done. Collaborator '{old_name}' renamed to '{new_name}'.")


if __name__ == "__main__":
    main()
