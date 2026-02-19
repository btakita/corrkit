"""Command reference for correspondence-kit."""

import sys

COMMANDS = [
    ("sync-gmail", "Incremental sync of Gmail threads to markdown", "uv run sync-gmail [--full]"),
    ("push-draft", "Save a draft to Gmail or send it", "uv run push-draft drafts/FILE.md [--send]"),
    ("collab-add", "Add a collaborator (creates shared repo + submodule)", "uv run collab-add NAME --label LABEL [--github-user USER | --pat] [--public]"),
    ("collab-sync", "Push/pull shared collaborator submodules", "uv run collab-sync [NAME]"),
    ("collab-status", "Check for pending changes in shared repos", "uv run collab-status"),
    ("collab-remove", "Remove a collaborator", "uv run collab-remove NAME [--delete-repo]"),
    ("audit-docs", "Audit instruction files for staleness", "uv run audit-docs"),
    ("help", "Show this command reference", "uv run help"),
]

DEV_COMMANDS = [
    ("pytest", "Run tests", "uv run pytest"),
    ("ruff check .", "Lint", "uv run ruff check ."),
    ("ruff format .", "Format", "uv run ruff format ."),
    ("ty check", "Type check", "uv run ty check"),
    ("poe precommit", "Run ty + ruff + tests", "uv run poe precommit"),
]


def main() -> None:
    filter_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if filter_arg and filter_arg not in ("--dev",):
        matches = [(n, d, u) for n, d, u in COMMANDS + DEV_COMMANDS if filter_arg in n]
        if matches:
            _print_table(matches)
        else:
            print(f"No command matching '{filter_arg}'")
            sys.exit(1)
        return

    print("correspondence-kit commands\n")
    _print_table(COMMANDS)

    if filter_arg == "--dev" or not filter_arg:
        print("\ndev commands\n")
        _print_table(DEV_COMMANDS)


def _print_table(rows: list[tuple[str, str, str]]) -> None:
    name_w = max(len(r[0]) for r in rows)
    desc_w = max(len(r[1]) for r in rows)
    for name, desc, usage in rows:
        print(f"  {name:<{name_w}}  {desc:<{desc_w}}  {usage}")