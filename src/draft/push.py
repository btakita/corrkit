"""
Push a draft markdown file as an email draft, or send it directly.

Default: creates a draft via IMAP APPEND.
With --send: sends the email immediately via SMTP.

Resolves the sending account from draft metadata (**Account** or **From**),
falling back to the default account in accounts.toml (or .env legacy).

Usage:
  corrkit push-draft correspondence/drafts/2026-02-19-example.md
  corrkit push-draft correspondence/drafts/2026-02-19-example.md --send
"""

import argparse
import re
import smtplib
import ssl as ssl_mod
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from imapclient import IMAPClient

_META_RE = re.compile(r"^\*\*(.+?)\*\*:\s*(.+)$")


def parse_draft(path: Path) -> tuple[dict[str, str], str, str]:
    """Parse a draft markdown file. Returns (meta, subject, body)."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    subject = ""
    for line in lines:
        if line.startswith("# "):
            subject = line[2:].strip()
            break

    meta: dict[str, str] = {}
    for line in lines:
        m = _META_RE.match(line)
        if m:
            meta[m.group(1)] = m.group(2).strip()

    if not meta.get("To"):
        raise SystemExit(f"Draft is missing **To**: field: {path}")

    # Body is everything after the first ---
    body_start = None
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break

    if body_start is None:
        raise SystemExit(f"Draft is missing --- separator: {path}")

    body = "\n".join(lines[body_start:]).strip()
    return meta, subject, body


def compose_email(
    meta: dict[str, str], subject: str, body: str, *, from_addr: str
) -> EmailMessage:
    """Compose an email message from draft metadata."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = meta["To"]
    msg["Subject"] = subject

    if cc := meta.get("CC"):
        msg["CC"] = cc
    if in_reply_to := meta.get("In-Reply-To"):
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    msg.set_content(body)
    return msg


def push_to_drafts(
    msg: EmailMessage,
    *,
    imap_host: str,
    imap_port: int,
    starttls: bool,
    user: str,
    password: str,
    drafts_folder: str,
) -> None:
    """APPEND an email to the drafts folder via IMAP."""
    use_ssl = not starttls
    ssl_context = None
    if starttls or (imap_host in ("127.0.0.1", "localhost")):
        ssl_context = ssl_mod.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl_mod.CERT_NONE
    with IMAPClient(
        imap_host, port=imap_port, ssl=use_ssl, ssl_context=ssl_context
    ) as imap:
        if starttls:
            imap.starttls(ssl_context=ssl_context)
        imap.login(user, password)
        imap.append(
            drafts_folder, msg.as_bytes(), flags=[], msg_time=datetime.now(tz=UTC)
        )


def send_email(
    msg: EmailMessage,
    *,
    smtp_host: str,
    smtp_port: int,
    user: str,
    password: str,
) -> None:
    """Send an email via SMTP."""
    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)


VALID_SEND_STATUSES = {"review", "approved"}


def _update_draft_status(path: Path, new_status: str) -> None:
    """Update the **Status** field in a draft file."""
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r"^(\*\*Status\*\*:\s*).+$",
        rf"\g<1>{new_status}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    path.write_text(updated, encoding="utf-8")


def _resolve_account(meta: dict[str, str]):
    """Resolve sending account from draft metadata."""
    from accounts import (
        get_account_for_email,
        get_default_account,
        load_accounts_or_env,
        resolve_password,
    )

    accounts = load_accounts_or_env()

    # Try **Account** field first
    acct_name = meta.get("Account", "")
    if acct_name and acct_name in accounts:
        acct = accounts[acct_name]
        return acct_name, acct, resolve_password(acct)

    # Try **From** field to match by email
    from_addr = meta.get("From", "")
    if from_addr:
        result = get_account_for_email(accounts, from_addr)
        if result:
            name, acct = result
            return name, acct, resolve_password(acct)

    # Fall back to default
    name, acct = get_default_account(accounts)
    return name, acct, resolve_password(acct)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push a draft markdown file as an email draft"
    )
    parser.add_argument("file", type=Path, help="Path to the draft markdown file")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send the email immediately instead of saving as a draft",
    )
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"File not found: {args.file}")

    meta, subject, body = parse_draft(args.file)

    # Validate Status for --send
    status = meta.get("Status", "").lower()
    if args.send and status and status not in VALID_SEND_STATUSES:
        raise SystemExit(
            f"Cannot send: Status is '{meta.get('Status')}'. "
            f"Must be one of: {', '.join(VALID_SEND_STATUSES)}"
        )

    acct_name, acct, password = _resolve_account(meta)

    print(f"Account: {acct_name} ({acct.user})")
    print(f"To:      {meta['To']}")
    print(f"Subject: {subject}")
    if meta.get("Author"):
        print(f"Author:  {meta['Author']}")
    if meta.get("Status"):
        print(f"Status:  {meta['Status']}")
    if meta.get("In-Reply-To"):
        print(f"Reply:   {meta['In-Reply-To']}")
    print(f"Body:    {body[:80]}{'...' if len(body) > 80 else ''}")
    print()

    msg = compose_email(meta, subject, body, from_addr=acct.user)

    if args.send:
        send_email(
            msg,
            smtp_host=acct.smtp_host,
            smtp_port=acct.smtp_port,
            user=acct.user,
            password=password,
        )
        _update_draft_status(args.file, "sent")
        print("Email sent. Status updated to 'sent'.")
    else:
        push_to_drafts(
            msg,
            imap_host=acct.imap_host,
            imap_port=acct.imap_port,
            starttls=acct.imap_starttls,
            user=acct.user,
            password=password,
            drafts_folder=acct.drafts_folder,
        )
        print("Draft created. Open your email drafts to review and send.")


if __name__ == "__main__":
    main()
