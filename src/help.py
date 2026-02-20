"""Command reference for correspondence-kit."""

import sys

COMMANDS = [
    ("sync [--full] [--account NAME]", "Sync email threads to markdown"),
    ("sync-auth", "Gmail OAuth setup"),
    ("list-folders [ACCOUNT]", "List IMAP folders for an account"),
    ("sync-gmail [--full] [--account NAME]", "Alias for sync"),
    (
        "push-draft FILE [--send]",
        "Save draft to Gmail (FILE: correspondence/drafts/*.md)",
    ),
    ("collab-add NAME --label LABEL", "Add a collaborator"),
    ("collab-sync [NAME]", "Push/pull shared submodules"),
    ("collab-status", "Check for pending changes"),
    ("collab-remove NAME [--delete-repo]", "Remove a collaborator"),
    ("audit-docs", "Audit instruction files"),
    ("help", "Show this reference"),
]

DEV_COMMANDS = [
    ("pytest", "Run tests"),
    ("ruff check .", "Lint"),
    ("ruff format .", "Format"),
    ("ty check", "Type check"),
    ("poe precommit", "Run ty + ruff + tests"),
]


def main() -> None:
    filter_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if filter_arg and filter_arg not in ("--dev",):
        matches = [
            (n, d)
            for n, d in COMMANDS + DEV_COMMANDS
            if filter_arg in n
        ]
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


def _print_table(rows: list[tuple[str, str]]) -> None:
    name_w = max(len(r[0]) for r in rows)
    for name, desc in rows:
        print(f"  {name:<{name_w}}  {desc}")