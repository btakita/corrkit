"""
Push a draft markdown file to Gmail as a draft, or send it directly.

Default: creates a Gmail draft for review.
With --send: sends the email immediately via SMTP.

Usage:
  uv run push-draft drafts/2026-02-19-example.md          # Save as Gmail draft
  uv run push-draft drafts/2026-02-19-example.md --send    # Send immediately
"""

import argparse
import os
import re
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from imapclient import IMAPClient

load_dotenv()

GMAIL_USER = os.environ["GMAIL_USER_EMAIL"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")

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


def compose_email(meta: dict[str, str], subject: str, body: str) -> EmailMessage:
    """Compose an email message from draft metadata."""
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = meta["To"]
    msg["Subject"] = subject

    if cc := meta.get("CC"):
        msg["CC"] = cc
    if in_reply_to := meta.get("In-Reply-To"):
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    msg.set_content(body)
    return msg


def push_to_drafts(msg: EmailMessage) -> None:
    """APPEND an email to [Gmail]/Drafts via IMAP."""
    with IMAPClient("imap.gmail.com", ssl=True) as imap:
        imap.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        imap.append(
            "[Gmail]/Drafts", msg.as_bytes(), flags=[], msg_time=datetime.now(tz=UTC)
        )


def send_email(msg: EmailMessage) -> None:
    """Send an email via Gmail SMTP."""
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def main() -> None:
    parser = argparse.ArgumentParser(description="Push a draft markdown file to Gmail")
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

    print(f"To:      {meta['To']}")
    print(f"Subject: {subject}")
    if meta.get("In-Reply-To"):
        print(f"Reply:   {meta['In-Reply-To']}")
    print(f"Body:    {body[:80]}{'...' if len(body) > 80 else ''}")
    print()

    msg = compose_email(meta, subject, body)

    if args.send:
        send_email(msg)
        print("Email sent.")
    else:
        push_to_drafts(msg)
        print("Draft created in Gmail. Open Gmail drafts to review and send.")


if __name__ == "__main__":
    main()
