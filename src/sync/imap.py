"""
Syncs email threads (by label) to local Markdown files under conversations/.
Supports multiple IMAP accounts via accounts.toml with provider presets.

Usage:
  corrkit sync                   # Sync all accounts
  corrkit sync --account personal # Sync one account
  corrkit sync --full            # Full re-sync (ignores saved state)
"""

import argparse
import email
import email.message
import os
import re
import ssl as ssl_mod
from datetime import UTC, datetime, timedelta
from email.header import decode_header as _decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

import msgspec
from imapclient import IMAPClient

from .types import AccountSyncState, LabelState, Message, SyncState, Thread
from .types import load_state as _load_state

STATE_FILE = Path("correspondence") / ".sync-state.json"
CONVERSATIONS_DIR = Path("correspondence") / "conversations"


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def load_state() -> SyncState:
    if STATE_FILE.exists():
        return _load_state(STATE_FILE.read_bytes())
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
                        part.get_content_charset() or "utf-8",
                        errors="replace",
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
    labels_str = ", ".join(thread.labels)
    accounts_str = ", ".join(thread.accounts)
    lines = [
        f"# {thread.subject}",
        "",
        f"**Labels**: {labels_str}",
        f"**Accounts**: {accounts_str}",
        f"**Thread ID**: {thread.id}",
        f"**Last updated**: {thread.last_date}",
        "",
    ]
    for msg in thread.messages:
        lines += [
            "---",
            "",
            f"## {msg.from_} \u2014 {msg.date}",
            "",
            msg.body.strip(),
            "",
        ]
    return "\n".join(lines)


def _parse_msg_date(date_str: str) -> datetime:
    """Parse an RFC 2822 date string, falling back to epoch on failure."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=UTC)


def _set_mtime(path: Path, date_str: str) -> None:
    """Set file mtime to the parsed date. Leaves atime unchanged."""
    dt = _parse_msg_date(date_str)
    if dt.year == 1970:
        return  # don't set mtime to epoch
    ts = dt.timestamp()
    os.utime(path, (path.stat().st_atime, ts))


# ---------------------------------------------------------------------------
# Markdown parser — read existing thread files back into Thread objects
# ---------------------------------------------------------------------------

_META_RE = re.compile(r"^\*\*(.+?)\*\*:\s*(.+)$")
_MSG_HEADER_RE = re.compile(r"^## (.+?) \u2014 (.+)$")


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
    last_date = meta.get("Last updated", "")

    # Parse labels (new multi-label format) with fallback to legacy
    labels_str = meta.get("Labels", "")
    if labels_str:
        labels = [lbl.strip() for lbl in labels_str.split(",") if lbl.strip()]
    else:
        # Backward compat: single **Label** field
        legacy = meta.get("Label", "")
        labels = [legacy] if legacy else []

    # Parse accounts
    accounts_str = meta.get("Accounts", "")
    if accounts_str:
        accounts = [a.strip() for a in accounts_str.split(",") if a.strip()]
    else:
        accounts = []

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
        subject=subject,
        labels=labels,
        accounts=accounts,
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


def _unique_slug(out_dir: Path, slug: str) -> str:
    """Return a slug that doesn't collide with existing files."""
    if not (out_dir / f"{slug}.md").exists():
        return slug
    n = 2
    while (out_dir / f"{slug}-{n}.md").exists():
        n += 1
    return f"{slug}-{n}"


# ---------------------------------------------------------------------------
# Merge + write
# ---------------------------------------------------------------------------


def _merge_message_to_file(
    out_dir: Path,
    label_name: str,
    account_name: str,
    message: Message,
    thread_key: str,
) -> Path | None:
    """Merge a single message into its thread file on disk.

    Returns the path of the written file, or None if deduplicated.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    existing_file = _find_thread_file(out_dir, thread_key)
    thread: Thread | None = None

    if existing_file:
        text = existing_file.read_text(encoding="utf-8")
        thread = parse_thread_markdown(text)

    if thread is None:
        thread = Thread(
            id=thread_key,
            subject=message.subject,
        )

    # Accumulate labels and accounts
    if label_name and label_name not in thread.labels:
        thread.labels.append(label_name)
    if account_name and account_name not in thread.accounts:
        thread.accounts.append(account_name)

    # Deduplicate by (from_, date)
    seen = {(m.from_, m.date) for m in thread.messages}
    if (message.from_, message.date) in seen:
        # Still update labels/accounts even if message is a dupe
        if existing_file:
            existing_file.write_text(thread_to_markdown(thread), encoding="utf-8")
            _set_mtime(existing_file, thread.last_date)
        return existing_file

    thread.messages.append(message)
    thread.messages.sort(key=lambda m: _parse_msg_date(m.date))
    thread.last_date = thread.messages[-1].date

    # Immutable slug filename — only set on first write
    if existing_file:
        file_path = existing_file
    else:
        slug = _unique_slug(out_dir, slugify(thread.subject))
        file_path = out_dir / f"{slug}.md"

    file_path.write_text(thread_to_markdown(thread), encoding="utf-8")
    _set_mtime(file_path, thread.last_date)

    print(f"  Wrote: {file_path.name}")
    return file_path


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def sync_label(
    imap: IMAPClient,
    label_name: str,
    account_name: str,
    acct_state: AccountSyncState,
    *,
    full: bool,
    sync_days: int = 3650,
    out_dir: Path | None = None,
    touched: set[Path] | None = None,
) -> None:
    print(f"Syncing label: {label_name}")

    try:
        folder_info = imap.select_folder(label_name, readonly=True)
    except Exception:
        print(f'  Label "{label_name}" not found \u2014 skipping')
        return

    uidvalidity = folder_info[b"UIDVALIDITY"]
    prior = acct_state.labels.get(label_name)

    # Decide: full fetch or incremental
    do_full = full or prior is None or prior.uidvalidity != uidvalidity

    if do_full:
        if prior is not None and prior.uidvalidity != uidvalidity:
            print("  UIDVALIDITY changed \u2014 doing full resync")
        elif full:
            print("  Full sync requested")
        else:
            print("  No prior state \u2014 doing full sync")

        since = (
            datetime.now(tz=UTC).replace(hour=0, minute=0, second=0)
            - timedelta(days=sync_days)
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
        acct_state.labels[label_name] = LabelState(
            uidvalidity=uidvalidity,
            last_uid=prior.last_uid if prior else 0,
        )
        return

    print(f"  Fetching {len(uids)} message(s)")

    if out_dir is None:
        out_dir = CONVERSATIONS_DIR
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

        file_path = _merge_message_to_file(
            out_dir, label_name, account_name, message, thread_key
        )
        if touched is not None and file_path is not None:
            touched.add(file_path)

        if uid > max_uid:
            max_uid = uid

    acct_state.labels[label_name] = LabelState(
        uidvalidity=uidvalidity,
        last_uid=max_uid,
    )


def _build_label_routes(account_name: str = "") -> dict[str, Path]:
    """Build label->output_dir map from collaborators.toml.

    Shared labels route to ``correspondence/for/{gh_user}/conversations/``.
    Private labels are not included (they go to the flat conversations/ dir).

    Labels support ``account:label`` syntax for per-label account binding.
    E.g. ``"proton-dev:INBOX"`` only matches when syncing the ``proton-dev``
    account, syncing the IMAP folder ``INBOX`` into the collaborator's dir.
    Plain labels (no colon) use the collaborator-level ``account`` field.
    """
    try:
        from collab import collab_dir, load_collaborators
    except ImportError:
        return {}

    routes: dict[str, Path] = {}
    for _gh_user, collab in load_collaborators().items():
        cdir = collab_dir(collab)
        for label in collab.labels:
            if ":" in label:
                # Per-label account binding: "account:folder"
                label_account, label_name = label.split(":", 1)
                if account_name and label_account != account_name:
                    continue
                routes[label_name] = cdir / "conversations"
            else:
                # Plain label — subject to collaborator-level account binding
                if account_name and collab.account and collab.account != account_name:
                    continue
                routes[label] = cdir / "conversations"
    return routes


def _cleanup_orphans(conversations_dir: Path, touched: set[Path]) -> None:
    """Delete conversation files not touched during a --full sync."""
    if not conversations_dir.exists():
        return
    for md_file in conversations_dir.glob("*.md"):
        if md_file not in touched:
            md_file.unlink()
            print(f"  Removed orphan: {md_file.name}")


def sync_account(
    account_name: str,
    *,
    host: str,
    port: int,
    starttls: bool,
    user: str,
    password: str,
    labels: list[str],
    sync_days: int,
    state: SyncState,
    full: bool,
    base_dir: Path = CONVERSATIONS_DIR,
    touched: set[Path] | None = None,
) -> None:
    """Sync all labels for one account."""
    acct_state = state.accounts.setdefault(account_name, AccountSyncState())

    # Build label routing from collaborators.toml
    routes = _build_label_routes(account_name)

    # Merge shared labels into sync set
    all_labels = list(dict.fromkeys(labels + list(routes.keys())))

    if not all_labels:
        print(f"  No labels configured for account '{account_name}' \u2014 skipping")
        return

    print(f"Connecting to {host}:{port} as {user}")

    use_ssl = not starttls
    # Protonmail Bridge (and other local servers) use self-signed certs
    ssl_context = None
    if starttls or (host in ("127.0.0.1", "localhost")):
        ssl_context = ssl_mod.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl_mod.CERT_NONE
    with IMAPClient(host, port=port, ssl=use_ssl, ssl_context=ssl_context) as imap:
        if starttls:
            imap.starttls(ssl_context=ssl_context)
        imap.login(user, password)
        for label in all_labels:
            shared_dir = routes.get(label)
            # Private labels → flat conversations dir
            # Shared labels → correspondence/for/{gh_user}/conversations/
            sync_label(
                imap,
                label,
                account_name,
                acct_state,
                full=full,
                sync_days=sync_days,
                out_dir=shared_dir if shared_dir else base_dir,
                touched=touched,
            )


def main() -> None:
    from accounts import load_accounts_or_env, resolve_password

    parser = argparse.ArgumentParser(description="Sync email threads to Markdown")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore saved state and re-fetch all messages",
    )
    parser.add_argument(
        "--account",
        help="Sync only the named account",
    )
    args = parser.parse_args()

    accounts = load_accounts_or_env()
    state = SyncState() if args.full else load_state()

    if args.account:
        if args.account not in accounts:
            raise SystemExit(
                f"Unknown account: {args.account}\n"
                f"Available: {', '.join(accounts.keys())}"
            )
        names = [args.account]
    else:
        names = list(accounts.keys())

    # Track touched files for --full orphan cleanup
    touched: set[Path] | None = set() if args.full else None

    for name in names:
        acct = accounts[name]
        print(f"\n=== Account: {name} ({acct.user}) ===")
        password = resolve_password(acct)
        sync_account(
            name,
            host=acct.imap_host,
            port=acct.imap_port,
            starttls=acct.imap_starttls,
            user=acct.user,
            password=password,
            labels=acct.labels,
            sync_days=acct.sync_days,
            state=state,
            full=args.full,
            touched=touched,
        )

    # Orphan cleanup on --full
    if touched is not None:
        _cleanup_orphans(CONVERSATIONS_DIR, touched)

    # Generate manifest
    _generate_manifest(CONVERSATIONS_DIR)

    save_state(state)
    print("\nSync complete.")


def _generate_manifest(conversations_dir: Path) -> None:
    """Generate manifest.toml from conversation files + contacts.toml."""
    if not conversations_dir.exists():
        return

    try:
        import tomli_w
    except ImportError:
        print("  Warning: tomli_w not installed, skipping manifest generation")
        return

    try:
        from contact import load_contacts

        contacts = load_contacts()
    except ImportError:
        contacts = {}

    # Build email→contact-name lookup
    email_to_contact: dict[str, str] = {}
    for cname, contact in contacts.items():
        for addr in contact.emails:
            email_to_contact[addr.lower()] = cname

    threads: dict[str, dict] = {}

    for md_file in sorted(conversations_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        thread = parse_thread_markdown(text)
        if thread is None:
            continue

        # Match contacts by sender emails
        thread_contacts: list[str] = []
        _email_re = re.compile(r"<([^>]+)>")
        for msg in thread.messages:
            m = _email_re.search(msg.from_)
            if m:
                addr = m.group(1).lower()
                cname = email_to_contact.get(addr)
                if cname and cname not in thread_contacts:
                    thread_contacts.append(cname)

        slug = md_file.stem
        threads[slug] = {
            "subject": thread.subject,
            "thread_id": thread.id,
            "labels": thread.labels,
            "accounts": thread.accounts,
            "last_updated": thread.last_date,
            "contacts": thread_contacts,
        }

    manifest_path = conversations_dir.parent / "manifest.toml"
    manifest_data = {"threads": threads}
    manifest_path.write_bytes(tomli_w.dumps(manifest_data).encode())
    print(f"  Generated {manifest_path}")


if __name__ == "__main__":
    main()
