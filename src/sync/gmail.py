"""
Syncs Gmail threads (by label) to local Markdown files under conversations/.
Uses IMAP with an App Password — no OAuth required.

Setup:
  1. Enable 2FA on your Google account
  2. Go to myaccount.google.com/apppasswords
  3. Create an app password named "correspondence"
  4. Add to .env: GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

Usage:
  uv run sync-gmail            # Incremental sync (fetches only new messages)
  uv run sync-gmail --full     # Full re-sync (ignores saved state)
"""

import argparse
import email
import email.message
import os
import re
from datetime import UTC, datetime, timedelta
from email.header import decode_header as _decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

import msgspec
from dotenv import load_dotenv
from imapclient import IMAPClient

from .types import LabelState, Message, SyncState, Thread

load_dotenv()

GMAIL_USER = os.environ["GMAIL_USER_EMAIL"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
SYNC_LABELS = [
    s.strip() for s in os.environ["GMAIL_SYNC_LABELS"].split(",") if s.strip()
]
SYNC_DAYS = int(os.getenv("GMAIL_SYNC_DAYS", "90"))

STATE_FILE = Path(".sync-state.json")

if not SYNC_LABELS:
    raise SystemExit("GMAIL_SYNC_LABELS must list at least one label")


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def load_state() -> SyncState:
    if STATE_FILE.exists():
        return msgspec.json.decode(STATE_FILE.read_bytes(), type=SyncState)
    return SyncState()


def save_state(state: SyncState) -> None:
    STATE_FILE.write_bytes(msgspec.json.encode(state))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def decode_header(value: str) -> str:
    parts = _decode_header(value)
    return "".join(
        part.decode(enc or "utf-8") if isinstance(part, bytes) else part
        for part, enc in parts
    )


def extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get(
                "Content-Disposition"
            ):
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    return payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode(
                msg.get_content_charset() or "utf-8", errors="replace"
            )
    return ""


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    result = text.strip("-")[:60]
    return result or "untitled"


def thread_key_from_subject(subject: str) -> str:
    return re.sub(r"^(re|fwd?):\s*", "", subject.lower().strip())


def thread_to_markdown(thread: Thread) -> str:
    lines = [
        f"# {thread.subject}",
        "",
        f"**Label**: {thread.label}",
        f"**Thread ID**: {thread.id}",
        f"**Last updated**: {thread.last_date}",
        "",
    ]
    for msg in thread.messages:
        lines += ["---", "", f"## {msg.from_} — {msg.date}", "", msg.body.strip(), ""]
    return "\n".join(lines)


def _parse_msg_date(date_str: str) -> datetime:
    """Parse an RFC 2822 date string, falling back to epoch on failure."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=UTC)


def date_prefix_from(date_str: str) -> str:
    dt = _parse_msg_date(date_str)
    if dt.year == 1970:
        return datetime.now(tz=UTC).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Markdown parser — read existing thread files back into Thread objects
# ---------------------------------------------------------------------------

_META_RE = re.compile(r"^\*\*(.+?)\*\*:\s*(.+)$")
_MSG_HEADER_RE = re.compile(r"^## (.+?) — (.+)$")


def parse_thread_markdown(text: str) -> Thread | None:
    """Parse a conversation markdown file back into a Thread."""
    lines = text.split("\n")

    # Extract subject from first H1
    subject = ""
    for line in lines:
        if line.startswith("# "):
            subject = line[2:].strip()
            break
    if not subject:
        return None

    # Extract metadata
    meta: dict[str, str] = {}
    for line in lines:
        m = _META_RE.match(line)
        if m:
            meta[m.group(1)] = m.group(2).strip()

    thread_id = meta.get("Thread ID", "")
    label = meta.get("Label", "")
    last_date = meta.get("Last updated", "")

    # Split into message sections on "## Sender — Date"
    messages: list[Message] = []
    current_from = ""
    current_date = ""
    body_lines: list[str] = []
    in_message = False

    for line in lines:
        m = _MSG_HEADER_RE.match(line)
        if m:
            # Save previous message
            if in_message:
                messages.append(
                    Message(
                        id="",
                        thread_id=thread_key_from_subject(subject),
                        from_=current_from,
                        date=current_date,
                        subject=subject,
                        body="\n".join(body_lines).strip(),
                    )
                )
            current_from = m.group(1)
            current_date = m.group(2)
            body_lines = []
            in_message = True
        elif in_message and line != "---":
            body_lines.append(line)

    # Save last message
    if in_message:
        messages.append(
            Message(
                id="",
                thread_id=thread_key_from_subject(subject),
                from_=current_from,
                date=current_date,
                subject=subject,
                body="\n".join(body_lines).strip(),
            )
        )

    return Thread(
        id=thread_id,
        label=label,
        subject=subject,
        messages=messages,
        last_date=last_date,
    )


def _find_thread_file(out_dir: Path, thread_id: str) -> Path | None:
    """Find an existing thread file by its Thread ID metadata."""
    if not out_dir.exists():
        return None
    for md_file in out_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        m = re.search(r"^\*\*Thread ID\*\*:\s*(.+)$", text, re.MULTILINE)
        if m and m.group(1).strip() == thread_id:
            return md_file
    return None


# ---------------------------------------------------------------------------
# Merge + write
# ---------------------------------------------------------------------------


def _merge_message_to_file(
    out_dir: Path, label_name: str, message: Message, thread_key: str
) -> None:
    """Merge a single message into its thread file on disk."""
    out_dir.mkdir(parents=True, exist_ok=True)

    existing_file = _find_thread_file(out_dir, thread_key)
    thread: Thread | None = None

    if existing_file:
        text = existing_file.read_text(encoding="utf-8")
        thread = parse_thread_markdown(text)

    if thread is None:
        thread = Thread(
            id=thread_key,
            label=label_name,
            subject=message.subject,
        )

    # Deduplicate by (from_, date)
    seen = {(m.from_, m.date) for m in thread.messages}
    if (message.from_, message.date) in seen:
        return

    thread.messages.append(message)
    thread.messages.sort(key=lambda m: _parse_msg_date(m.date))
    thread.last_date = thread.messages[-1].date

    new_prefix = date_prefix_from(thread.last_date)
    new_filename = f"{new_prefix}-{slugify(thread.subject)}.md"
    new_path = out_dir / new_filename

    new_path.write_text(thread_to_markdown(thread), encoding="utf-8")

    # Remove old file if the filename changed
    if existing_file and existing_file != new_path:
        existing_file.unlink()
        print(f"  Renamed: {existing_file.name} → {new_filename}")
    else:
        print(f"  Wrote: conversations/{label_name}/{new_filename}")


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def sync_label(
    imap: IMAPClient,
    label_name: str,
    state: SyncState,
    *,
    full: bool,
    out_dir: Path | None = None,
) -> None:
    print(f"Syncing label: {label_name}")

    try:
        folder_info = imap.select_folder(label_name, readonly=True)
    except Exception:
        print(f'  Label "{label_name}" not found — skipping')
        return

    uidvalidity = folder_info[b"UIDVALIDITY"]
    prior = state.labels.get(label_name)

    # Decide: full fetch or incremental
    do_full = full or prior is None or prior.uidvalidity != uidvalidity

    if do_full:
        if prior is not None and prior.uidvalidity != uidvalidity:
            print("  UIDVALIDITY changed — doing full resync")
        elif full:
            print("  Full sync requested")
        else:
            print("  No prior state — doing full sync")

        since = (
            datetime.now(tz=UTC).replace(hour=0, minute=0, second=0)
            - timedelta(days=SYNC_DAYS)
        ).strftime("%d-%b-%Y")
        uids = imap.search(["SINCE", since])
    else:
        # Incremental: fetch UIDs after last_uid
        assert prior is not None  # guaranteed by do_full logic above
        uids = imap.search(["UID", f"{prior.last_uid + 1}:*"])
        # IMAP UID search always returns at least one UID — filter out already-seen
        uids = [u for u in uids if u > prior.last_uid]

    if not uids:
        print("  No new messages")
        state.labels[label_name] = LabelState(
            uidvalidity=uidvalidity,
            last_uid=prior.last_uid if prior else 0,
        )
        return

    print(f"  Fetching {len(uids)} message(s)")

    if out_dir is None:
        out_dir = Path("conversations") / label_name
    max_uid = prior.last_uid if prior else 0

    for uid in uids:
        msg_data = imap.fetch([uid], "RFC822")
        if uid not in msg_data:
            continue

        raw = msg_data[uid][b"RFC822"]
        msg = email.message_from_bytes(raw)

        subject = decode_header(msg.get("Subject", "(no subject)"))
        from_ = decode_header(msg.get("From", ""))
        date = msg.get("Date", "")
        thread_key = thread_key_from_subject(subject)
        body = extract_body(msg)

        message = Message(
            id=str(uid),
            thread_id=thread_key,
            from_=from_,
            date=date,
            subject=subject,
            body=body,
        )

        _merge_message_to_file(out_dir, label_name, message, thread_key)

        if uid > max_uid:
            max_uid = uid

    state.labels[label_name] = LabelState(
        uidvalidity=uidvalidity,
        last_uid=max_uid,
    )


def _build_label_routes() -> dict[str, Path]:
    """Build label→output_dir map from collaborators.toml.

    Shared labels route to shared/{name}/conversations/{label}/.
    Private labels route to conversations/{label}/ (returned as None → default).
    """
    try:
        from collab import load_collaborators
    except ImportError:
        return {}

    routes: dict[str, Path] = {}
    for name, collab in load_collaborators().items():
        for label in collab.labels:
            routes[label] = Path("shared") / name / "conversations" / label
    return routes


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Gmail threads to Markdown")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore saved state and re-fetch all messages",
    )
    args = parser.parse_args()

    state = SyncState() if args.full else load_state()

    # Build label routing from collaborators.toml
    routes = _build_label_routes()

    # Merge shared labels into sync set
    all_labels = list(dict.fromkeys(SYNC_LABELS + list(routes.keys())))

    with IMAPClient("imap.gmail.com", ssl=True) as imap:
        imap.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        for label in all_labels:
            out_dir = routes.get(label)  # None → default conversations/{label}
            sync_label(imap, label, state, full=args.full, out_dir=out_dir)

    save_state(state)
    print("Sync complete.")


if __name__ == "__main__":
    main()
