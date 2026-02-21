"""
Remove a collaborator: deinit submodule, remove from config.

Usage:
  corrkit for remove alex-gh
  corrkit for remove alex-gh --delete-repo   # Also delete the GitHub repo
"""

import argparse
import subprocess
import sys
from pathlib import Path

from . import collab_dir, load_collaborators, save_collaborators


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove a collaborator")
    parser.add_argument("name", help="Collaborator GitHub username to remove")
    parser.add_argument(
        "--delete-repo",
        action="store_true",
        help="Also delete the GitHub repo (requires confirmation)",
    )
    args = parser.parse_args()

    name: str = args.name
    collabs = load_collaborators()

    if name not in collabs:
        print(f"Collaborator '{name}' not found in collaborators.toml")
        sys.exit(1)

    collab = collabs[name]
    sub_path = collab_dir(collab)

    # 1. Deinit and remove submodule
    if sub_path.exists():
        print(f"Removing submodule: {sub_path}")
        _run(["git", "submodule", "deinit", "-f", str(sub_path)])
        _run(["git", "rm", "-f", str(sub_path)])
    else:
        print(f"Submodule {sub_path} not found on disk -- skipping git cleanup")

    # Clean up .git/modules entry
    modules_path = Path(".git/modules") / str(sub_path)
    if modules_path.exists():
        _run(["rm", "-rf", str(modules_path)])

    # 2. Remove from collaborators.toml
    del collabs[name]
    save_collaborators(collabs)
    print(f"Removed '{name}' from collaborators.toml")

    # 3. Optionally delete the GitHub repo
    if args.delete_repo:
        confirm = input(
            f"Delete GitHub repo {collab.repo}? This cannot be undone. [y/N] "
        )
        if confirm.lower() == "y":
            _run(["gh", "repo", "delete", collab.repo, "--yes"])
            print(f"Deleted GitHub repo: {collab.repo}")
        else:
            print("Skipped repo deletion")

    print(f"Done. Collaborator '{name}' removed.")


if __name__ == "__main__":
    main()
