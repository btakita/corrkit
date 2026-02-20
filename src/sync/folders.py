"""List IMAP folders for a configured account.

Usage:
  corrkit list-folders <account-name>
  corrkit list-folders              # lists available account names
"""

import argparse
import ssl as ssl_mod

from imapclient import IMAPClient

from accounts import load_accounts_or_env, resolve_password


def main() -> None:
    parser = argparse.ArgumentParser(description="List IMAP folders for an account")
    parser.add_argument("account", nargs="?", help="Account name from accounts.toml")
    args = parser.parse_args()

    accounts = load_accounts_or_env()

    if not args.account:
        print("Available accounts:")
        for name, acct in accounts.items():
            print(f"  {name:<20} {acct.user}")
        return

    if args.account not in accounts:
        raise SystemExit(
            f"Unknown account: {args.account}\n"
            f"Available: {', '.join(accounts.keys())}"
        )

    acct = accounts[args.account]
    password = resolve_password(acct)

    ssl_context = None
    if acct.imap_starttls or acct.imap_host in ("127.0.0.1", "localhost"):
        ssl_context = ssl_mod.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl_mod.CERT_NONE

    use_ssl = not acct.imap_starttls
    print(f"Connecting to {acct.imap_host}:{acct.imap_port} as {acct.user}\n")

    with IMAPClient(
        acct.imap_host, port=acct.imap_port,
        ssl=use_ssl, ssl_context=ssl_context,
    ) as imap:
        if acct.imap_starttls:
            imap.starttls(ssl_context=ssl_context)
        imap.login(acct.user, password)
        for flags, _delim, folder_name in imap.list_folders():
            flag_str = ", ".join(
                f.decode() if isinstance(f, bytes) else str(f) for f in flags
            )
            print(f"  {folder_name:<40} [{flag_str}]")


if __name__ == "__main__":
    main()
