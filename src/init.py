"""
Initialize a new corrkit data directory with config and folder structure.

Usage:
  corrkit init --user you@gmail.com
  corrkit init --user you@pm.me --provider protonmail-bridge \
    --password-cmd "pass email/pm"
  corrkit init --user you@gmail.com --data-dir ~/my-correspondence --sync
"""

import argparse
import os
import sys
from pathlib import Path

import tomli_w

from accounts import PROVIDER_PRESETS


def _create_dirs(data_dir: Path) -> None:
    """Create the data directory structure with .gitkeep files."""
    for sub in ("conversations", "drafts", "contacts"):
        d = data_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()


def _generate_accounts_toml(
    *,
    user: str,
    provider: str,
    password_cmd: str,
    labels: list[str],
    github_user: str,
    name: str,
) -> bytes:
    """Generate accounts.toml content."""
    doc: dict[str, object] = {}

    # Owner section
    owner: dict[str, str] = {"github_user": github_user} if github_user else {}
    if name:
        owner["name"] = name
    if owner:
        doc["owner"] = owner

    # Account section
    account: dict[str, object] = {
        "provider": provider,
        "user": user,
        "labels": labels,
        "default": True,
    }
    if password_cmd:
        account["password_cmd"] = password_cmd
    doc["accounts"] = {"default": account}

    return tomli_w.dumps(doc).encode()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize a new corrkit data directory"
    )
    parser.add_argument("--user", required=True, help="Email address")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "Documents" / "correspondence",
        help="Data directory path (default: ~/Documents/correspondence)",
    )
    parser.add_argument(
        "--provider",
        default="gmail",
        choices=["gmail", "protonmail-bridge", "imap"],
        help="Email provider (default: gmail)",
    )
    parser.add_argument(
        "--password-cmd",
        default="",
        help="Shell command to retrieve password",
    )
    parser.add_argument(
        "--labels",
        default="correspondence",
        help="Comma-separated labels (default: correspondence)",
    )
    parser.add_argument(
        "--github-user",
        default="",
        help="GitHub username (for collaborator features)",
    )
    parser.add_argument(
        "--name",
        default="",
        help="Display name",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run first sync after setup",
    )
    parser.add_argument(
        "--space",
        default="default",
        help="Space name to register in app config (default: 'default')",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing accounts.toml",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir.expanduser()
    labels = [s.strip() for s in args.labels.split(",") if s.strip()]

    accounts_path = data_dir / "accounts.toml"
    if accounts_path.exists() and not args.force:
        print(f"accounts.toml already exists at {accounts_path}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    # 1. Create directory structure
    _create_dirs(data_dir)
    print(f"Created {data_dir}/{{conversations,drafts,contacts}}/")

    # 2. Generate accounts.toml
    content = _generate_accounts_toml(
        user=args.user,
        provider=args.provider,
        password_cmd=args.password_cmd,
        labels=labels,
        github_user=args.github_user,
        name=args.name,
    )
    accounts_path.write_bytes(content)
    print(f"Created {accounts_path}")

    # 3. Create empty collaborators.toml and contacts.toml
    for name in ("collaborators.toml", "contacts.toml"):
        p = data_dir / name
        if not p.exists():
            p.write_text("", encoding="utf-8")
            print(f"Created {p}")

    # 4. Register space in app config
    import app_config

    app_config.add_space(args.space, str(data_dir))
    print(f"Registered space '{args.space}' → {data_dir}")

    # 5. Provider-specific guidance
    if args.provider == "gmail" and not args.password_cmd:
        print()
        print("Gmail setup:")
        print("  Option A: App password — https://myaccount.google.com/apppasswords")
        print('    Add password_cmd = "pass email/personal" to accounts.toml')
        print(
            "  Option B: OAuth — run 'corrkit sync-auth' after placing credentials.json"
        )

    # 6. Optional first sync
    if args.sync:
        os.environ["CORRKIT_DATA"] = str(data_dir)
        from sync.imap import main as sync_main

        print()
        sys.argv = ["sync"]
        sync_main()

    if not args.sync:
        print()
        print("Done! Next steps:")
        print(f"  - Edit {accounts_path} with your credentials")
        if args.provider == "gmail" and not args.password_cmd:
            print("  - Set up app password or OAuth (see above)")
        preset = PROVIDER_PRESETS.get(args.provider, {})
        if not preset and args.provider == "imap":
            print("  - Add imap_host, smtp_host to accounts.toml")
        print(f"  - Run: CORRKIT_DATA={data_dir} corrkit sync")


if __name__ == "__main__":
    main()
