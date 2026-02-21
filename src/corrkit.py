"""Unified CLI dispatcher for corrkit.

Usage:
    corrkit <subcommand> [args...]
    corrkit --help
"""

import importlib
import sys

SUBCOMMANDS: dict[str, tuple[str, str]] = {
    "sync": ("sync.imap", "main"),
    "sync-auth": ("sync.auth", "main"),
    "list-folders": ("sync.folders", "main"),
    "sync-gmail": ("sync.imap", "main"),  # alias for sync
    "push-draft": ("draft.push", "main"),
    "collab-add": ("collab.add", "main"),
    "collab-sync": ("collab.sync", "main"),
    "collab-status": ("collab.sync", "status"),
    "collab-remove": ("collab.remove", "main"),
    "collab-rename": ("collab.rename", "main"),
    "collab-reset": ("collab.reset", "main"),
    "find-unanswered": ("collab.find_unanswered", "main"),
    "validate-draft": ("collab.validate_draft", "main"),
    "add-label": ("accounts", "add_label_main"),
    "contact-add": ("contact.add", "main"),
    "watch": ("watch", "main"),
    "audit-docs": ("audit_docs", "main"),
    "help": ("help", "main"),
}


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        _show_help()
        return

    subcmd = args[0]

    if subcmd not in SUBCOMMANDS:
        print(f"Unknown command: {subcmd}", file=sys.stderr)
        print(file=sys.stderr)
        _show_help(file=sys.stderr)
        sys.exit(1)

    module_path, func_name = SUBCOMMANDS[subcmd]

    # Rewrite sys.argv so the subcommand's argparse sees the right program name
    sys.argv = [subcmd, *args[1:]]

    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name)
    fn()


def _show_help(file=None) -> None:
    if file is None:
        file = sys.stdout
    import help as help_mod

    if file is sys.stdout:
        # Reset sys.argv so help:main doesn't see --help as a filter
        sys.argv = ["help"]
        help_mod.main()
    else:
        # For stderr, reuse the help module's data directly
        print("corrkit commands\n", file=file)
        for name, desc in help_mod.COMMANDS:
            print(f"  {name}  {desc}", file=file)
