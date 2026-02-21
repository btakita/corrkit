"""Tests for sync state format: legacy migration, new format, round-trip."""

import msgspec

from sync.types import AccountSyncState, LabelState, SyncState, load_state

# ---------------------------------------------------------------------------
# Legacy format migration
# ---------------------------------------------------------------------------


def test_legacy_flat_labels_migrated():
    """Old format with top-level 'labels' dict gets migrated to accounts._legacy."""
    legacy = {
        "labels": {
            "correspondence": {"uidvalidity": 1, "last_uid": 500},
            "important": {"uidvalidity": 2, "last_uid": 300},
        }
    }
    state = load_state(msgspec.json.encode(legacy))
    assert state.labels == {}  # cleared
    assert "_legacy" in state.accounts
    assert "correspondence" in state.accounts["_legacy"].labels
    assert state.accounts["_legacy"].labels["correspondence"].last_uid == 500
    assert state.accounts["_legacy"].labels["important"].uidvalidity == 2


def test_legacy_empty_stays_empty():
    state = load_state(b"{}")
    assert state.accounts == {}
    assert state.labels == {}


# ---------------------------------------------------------------------------
# New format
# ---------------------------------------------------------------------------


def test_new_format_loads_directly():
    new = {
        "accounts": {
            "personal": {
                "labels": {
                    "inbox": {"uidvalidity": 1, "last_uid": 100},
                }
            },
            "proton": {
                "labels": {
                    "private": {"uidvalidity": 3, "last_uid": 42},
                }
            },
        }
    }
    state = load_state(msgspec.json.encode(new))
    assert "personal" in state.accounts
    assert "proton" in state.accounts
    assert state.accounts["personal"].labels["inbox"].last_uid == 100
    assert state.labels == {}  # no migration needed


def test_new_format_no_migration_when_accounts_present():
    """If both accounts and labels exist, accounts wins — labels left as-is."""
    mixed = {
        "accounts": {
            "personal": {"labels": {"inbox": {"uidvalidity": 1, "last_uid": 100}}}
        },
        "labels": {
            "old": {"uidvalidity": 9, "last_uid": 999},
        },
    }
    state = load_state(msgspec.json.encode(mixed))
    # accounts present → no migration, labels left as-is
    assert "personal" in state.accounts
    assert state.labels == {"old": LabelState(uidvalidity=9, last_uid=999)}


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip():
    original = SyncState(
        accounts={
            "gmail": AccountSyncState(
                labels={"inbox": LabelState(uidvalidity=5, last_uid=200)}
            ),
        }
    )
    encoded = msgspec.json.encode(original)
    decoded = load_state(encoded)
    assert decoded.accounts["gmail"].labels["inbox"].last_uid == 200
    assert decoded.labels == {}
