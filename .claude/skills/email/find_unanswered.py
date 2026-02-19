"""
List synced threads where the last message is not from you —
i.e. threads awaiting your reply.

Usage: uv run .claude/skills/email/find_unanswered.py
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

USER_EMAIL = os.getenv("GMAIL_USER_EMAIL", "").lower()
if not USER_EMAIL:
    print("GMAIL_USER_EMAIL not set in .env", file=sys.stderr)
    sys.exit(1)

CONVERSATIONS = Path("conversations")
if not CONVERSATIONS.exists():
    print("No conversations/ directory found. Run sync first.", file=sys.stderr)
    sys.exit(1)

# Match "## Sender Name <email@example.com> — Date" or "## Name — Date"
SENDER_RE = re.compile(r"^## (.+?) —", re.MULTILINE)


def last_sender(text: str) -> str:
    matches = SENDER_RE.findall(text)
    return matches[-1].strip() if matches else ""


unanswered: list[tuple[str, str, str]] = []  # (label, filename, last_sender)

thread_files = sorted(
    CONVERSATIONS.rglob("*.md"), key=lambda p: p.name, reverse=True
)
for thread_file in thread_files:
    text = thread_file.read_text(encoding="utf-8")
    sender = last_sender(text)
    # Consider it unanswered if the last sender doesn't contain the user's email or name
    if USER_EMAIL not in sender.lower():
        label = thread_file.parent.name
        unanswered.append((label, thread_file.name, sender))

if not unanswered:
    print("No unanswered threads found.")
    sys.exit(0)

print(f"Unanswered threads ({len(unanswered)}):\n")
for label, filename, sender in unanswered:
    print(f"  [{label}] {filename}")
    print(f"           Last from: {sender}")
    print()
