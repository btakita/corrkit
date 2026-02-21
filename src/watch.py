"""IMAP polling daemon — syncs email and pushes to shared repos on an interval."""

import argparse
import platform
import signal
import subprocess
import sys
import threading

import msgspec

from accounts import load_accounts_or_env, load_watch_config, resolve_password
from collab import load_collaborators
from collab.sync import _sync_one
from sync.imap import STATE_FILE, sync_account
from sync.types import SyncState
from sync.types import load_state as _decode_state

_shutdown = threading.Event()


def _notify(title: str, body: str) -> None:
    """Best-effort desktop notification. Silently degrades if tool not installed."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f"display notification {body!r} with title {title!r}",
                ],
                check=False,
                capture_output=True,
            )
        elif system == "Linux":
            subprocess.run(
                ["notify-send", title, body],
                check=False,
                capture_output=True,
            )
    except FileNotFoundError:
        pass


def _snapshot_uids(state: SyncState) -> dict[str, dict[str, int]]:
    """Snapshot {account: {label: last_uid}} from current sync state."""
    snap: dict[str, dict[str, int]] = {}
    for acct_name, acct_state in state.accounts.items():
        snap[acct_name] = {
            label: ls.last_uid for label, ls in acct_state.labels.items()
        }
    return snap


def _count_new_messages(
    before: dict[str, dict[str, int]], after: dict[str, dict[str, int]]
) -> int:
    """Count labels where last_uid increased (proxy for new messages)."""
    count = 0
    for acct_name, labels in after.items():
        before_acct = before.get(acct_name, {})
        for label, uid in labels.items():
            if uid > before_acct.get(label, 0):
                count += 1
    return count


def _load_state() -> SyncState:
    """Load sync state from disk, or return empty state."""
    if STATE_FILE.exists():
        return _decode_state(STATE_FILE.read_bytes())
    return SyncState()


def _save_state(state: SyncState) -> None:
    """Write sync state to disk."""
    STATE_FILE.write_bytes(msgspec.json.encode(state))


def _sync_collaborators() -> None:
    """Run 'for sync' for all collaborators with pending changes."""
    from collab import collab_dir

    collabs = load_collaborators()
    if not collabs:
        return
    for name, collab in collabs.items():
        sub_path = collab_dir(collab)
        if not sub_path.exists():
            continue
        # Check if submodule has changes
        result = subprocess.run(
            ["git", "-C", str(sub_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            _sync_one(name)


def _poll_once(*, notify_enabled: bool) -> int:
    """One sync + 'for sync' cycle. Returns count of labels with new messages."""
    accounts = load_accounts_or_env()
    state = _load_state()

    before = _snapshot_uids(state)

    for acct_name, acct in accounts.items():
        print(f"\n=== Account: {acct_name} ({acct.user}) ===")
        try:
            password = resolve_password(acct)
            sync_account(
                acct_name,
                host=acct.imap_host,
                port=acct.imap_port,
                starttls=acct.imap_starttls,
                user=acct.user,
                password=password,
                labels=acct.labels,
                sync_days=acct.sync_days,
                state=state,
                full=False,
            )
        except Exception as exc:
            print(f"  Error syncing {acct_name}: {exc}", file=sys.stderr)
            continue

    _save_state(state)

    after = _snapshot_uids(state)
    new_count = _count_new_messages(before, after)

    if new_count > 0:
        print(f"\n{new_count} label(s) with new messages")
        _sync_collaborators()
        if notify_enabled:
            _notify("corrkit", f"{new_count} label(s) with new messages")
    else:
        print("\nNo new messages")

    return new_count


def main() -> None:
    parser = argparse.ArgumentParser(description="IMAP polling daemon")
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Poll interval in seconds (overrides accounts.toml)",
    )
    args = parser.parse_args()

    config = load_watch_config()
    interval = args.interval if args.interval is not None else config.poll_interval

    # Clean shutdown on SIGTERM/SIGINT
    def _handle_signal(signum: int, frame: object) -> None:
        print(f"\nReceived signal {signum}, shutting down...")
        _shutdown.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    print(f"corrkit watch: polling every {interval}s (Ctrl-C to stop)")

    while not _shutdown.is_set():
        try:
            _poll_once(notify_enabled=config.notify)
        except Exception as exc:
            print(f"\nPoll error: {exc}", file=sys.stderr)

        if _shutdown.wait(timeout=interval):
            break

    print("corrkit watch: stopped")


if __name__ == "__main__":
    main()
