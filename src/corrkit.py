"""Unified CLI dispatcher for corrkit.

Usage:
    corrkit <subcommand> [args...]
    corrkit for <subcommand> [args...]
    corrkit by <subcommand> [args...]
    corrkit --help
"""

import importlib
import sys

SUBCOMMANDS: dict[str, tuple[str, str]] = {
    "init": ("init", "main"),
    "sync": ("sync.imap", "main"),
    "sync-auth": ("sync.auth", "main"),
    "list-folders": ("sync.folders", "main"),
    "sync-gmail": ("sync.imap", "main"),  # alias for sync
    "push-draft": ("draft.push", "main"),
    "add-label": ("accounts", "add_label_main"),
    "contact-add": ("contact.add", "main"),
    "watch": ("watch", "main"),
    "audit-docs": ("audit_docs", "main"),
    "help": ("help", "main"),
}

NESTED_COMMANDS: dict[str, dict[str, tuple[str, str]]] = {
    "for": {
        "add": ("collab.add", "main"),
        "remove": ("collab.remove", "main"),
        "rename": ("collab.rename", "main"),
        "sync": ("collab.sync", "main"),
        "status": ("collab.sync", "status_main"),
        "reset": ("collab.reset", "main"),
    },
    "by": {
        "find-unanswered": ("collab.find_unanswered", "main"),
        "validate-draft": ("collab.validate_draft", "main"),
    },
}


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        _show_help()
        return

    cmd = args[0]

    # Nested commands: corrkit for add ..., corrkit by find-unanswered ...
    if cmd in NESTED_COMMANDS:
        if len(args) < 2 or args[1] in ("--help", "-h"):
            _show_help()
            return

        subcmd = args[1]
        subcommands = NESTED_COMMANDS[cmd]

        if subcmd not in subcommands:
            print(f"Unknown command: {cmd} {subcmd}", file=sys.stderr)
            print(file=sys.stderr)
            _show_help(file=sys.stderr)
            sys.exit(1)

        module_path, func_name = subcommands[subcmd]
        sys.argv = [f"{cmd} {subcmd}", *args[2:]]
        mod = importlib.import_module(module_path)
        fn = getattr(mod, func_name)
        fn()
        return

    # Flat commands
    if cmd not in SUBCOMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(file=sys.stderr)
        _show_help(file=sys.stderr)
        sys.exit(1)

    module_path, func_name = SUBCOMMANDS[cmd]

    # Rewrite sys.argv so the subcommand's argparse sees the right program name
    sys.argv = [cmd, *args[1:]]

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
        print("\ncollaborator commands (for = outbound, by = inbound)\n", file=file)
        for name, desc in help_mod.FOR_COMMANDS:
            print(f"  {name}  {desc}", file=file)
        for name, desc in help_mod.BY_COMMANDS:
            print(f"  {name}  {desc}", file=file)
