"""
Find threads where the last message is not from Brian --
i.e. threads awaiting a reply.

Usage:
  corrkit find-unanswered
  corrkit find-unanswered --from "Brian"
"""

import argparse
import re
import sys
from pathlib import Path

# Match "## Sender Name <email@example.com> — Date" or "## Name — Date"
SENDER_RE = re.compile(r"^## (.+?) \u2014", re.MULTILINE)

# Date from "## Sender — YYYY-MM-DD ..." or from **Last updated**: line
DATE_RE = re.compile(r"\*\*Last updated\*\*:\s*(\S+)")


def last_sender(text: str) -> str:
    matches = SENDER_RE.findall(text)
    return matches[-1].strip() if matches else ""


def thread_date(text: str) -> str:
    m = DATE_RE.search(text)
    return m.group(1) if m else ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find threads awaiting a reply"
    )
    parser.add_argument(
        "--from",
        dest="from_name",
        default="Brian",
        help="Name to match as 'your' messages (default: Brian)",
    )
    args = parser.parse_args()

    conversations = Path("conversations")
    if not conversations.exists():
        print(
            "No conversations/ directory found. "
            "Make sure you're in the shared repo root.",
            file=sys.stderr,
        )
        sys.exit(1)

    from_lower = args.from_name.lower()

    unanswered: list[tuple[str, str, str, str]] = []  # (date, label, file, sender)

    for thread_file in sorted(conversations.rglob("*.md")):
        text = thread_file.read_text(encoding="utf-8")
        sender = last_sender(text)
        if sender and from_lower not in sender.lower():
            label = thread_file.parent.name
            date = thread_date(text) or "unknown"
            unanswered.append((date, label, thread_file.name, sender))

    if not unanswered:
        print("No unanswered threads found.")
        sys.exit(0)

    # Sort by date descending (newest first)
    unanswered.sort(key=lambda x: x[0], reverse=True)

    print(f"Unanswered threads ({len(unanswered)}):\n")
    for date, label, filename, sender in unanswered:
        print(f"  [{label}] {filename}")
        print(f"           Last from: {sender} ({date})")
        print()


if __name__ == "__main__":
    main()
