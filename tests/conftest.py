"""Shared fixtures. Sets env vars needed by modules that read them at import time."""

import os

# gmail.py and draft/push.py read these at module level, so they must be set
# before those modules are first imported.
os.environ.setdefault("GMAIL_USER_EMAIL", "test@example.com")
os.environ.setdefault("GMAIL_APP_PASSWORD", "test-password")
os.environ.setdefault("GMAIL_SYNC_LABELS", "correspondence")
