"""Command reference for corrkit."""

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
    ("add-label LABEL --account NAME", "Add a label to an account's sync config"),
    ("contact-add NAME --email EMAIL", "Add a contact with context docs"),
    ("watch [--interval N]", "Poll IMAP and sync on an interval"),
    ("audit-docs", "Audit instruction files"),
    ("help", "Show this reference"),
]

FOR_COMMANDS = [
    ("for add NAME --label LABEL", "Add a collaborator"),
    ("for sync [NAME]", "Push/pull shared submodules"),
    ("for status", "Check for pending changes"),
    ("for remove NAME [--delete-repo]", "Remove a collaborator"),
    ("for rename OLD NEW", "Rename a collaborator directory"),
    ("for reset [NAME] [--no-sync]", "Pull, regenerate templates, commit & push"),
]

BY_COMMANDS = [
    ("by find-unanswered [--from NAME]", "Find threads awaiting a reply"),
    ("by validate-draft FILE [FILE...]", "Validate draft markdown files"),
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
        all_cmds = COMMANDS + FOR_COMMANDS + BY_COMMANDS + DEV_COMMANDS
        matches = [(n, d) for n, d in all_cmds if filter_arg in n]
        if matches:
            _print_table(matches)
        else:
            print(f"No command matching '{filter_arg}'")
            sys.exit(1)
        return

    print("corrkit commands\n")
    _print_table(COMMANDS)

    print("\ncollaborator commands (for = outbound, by = inbound)\n")
    _print_table(FOR_COMMANDS + BY_COMMANDS)

    if filter_arg == "--dev" or not filter_arg:
        print("\ndev commands\n")
        _print_table(DEV_COMMANDS)


def _print_table(rows: list[tuple[str, str]]) -> None:
    name_w = max(len(r[0]) for r in rows)
    for name, desc in rows:
        print(f"  {name:<{name_w}}  {desc}")
