"""Path resolution for corrkit data and config directories.

Resolution order for data directory:
  1. correspondence/ in cwd (developer workflow)
  2. CORRKIT_DATA environment variable
  3. ~/Documents/correspondence (general user default)

Config directory:
  - If correspondence/ exists in cwd → Path(".") (developer workflow)
  - Otherwise → same as data_dir() (general user: config inside data dir)
"""

import os
from pathlib import Path


def data_dir() -> Path:
    """Return the data directory path."""
    local = Path("correspondence")
    if local.is_dir():
        return local
    env = os.environ.get("CORRKIT_DATA")
    if env:
        return Path(env)
    return Path.home() / "Documents" / "correspondence"


def config_dir() -> Path:
    """Return the config directory path."""
    if Path("correspondence").is_dir():
        return Path(".")
    return data_dir()


# ---------------------------------------------------------------------------
# Derived helpers — data paths
# ---------------------------------------------------------------------------


def conversations_dir() -> Path:
    return data_dir() / "conversations"


def drafts_dir() -> Path:
    return data_dir() / "drafts"


def contacts_dir() -> Path:
    return data_dir() / "contacts"


def collab_for_dir(gh_user: str) -> Path:
    return data_dir() / "for" / gh_user.lower()


def sync_state_file() -> Path:
    return data_dir() / ".sync-state.json"


def manifest_file() -> Path:
    return data_dir() / "manifest.toml"


# ---------------------------------------------------------------------------
# Derived helpers — config paths
# ---------------------------------------------------------------------------


def accounts_toml() -> Path:
    return config_dir() / "accounts.toml"


def collaborators_toml() -> Path:
    return config_dir() / "collaborators.toml"


def contacts_toml() -> Path:
    return config_dir() / "contacts.toml"


def voice_md() -> Path:
    return config_dir() / "voice.md"


def credentials_json() -> Path:
    return config_dir() / "credentials.json"
