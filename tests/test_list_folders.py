"""Tests for list-folders command."""

from unittest.mock import MagicMock, patch

import pytest

from accounts import Account
from sync.folders import main

GMAIL_ACCOUNT = Account(
    provider="gmail",
    user="test@example.com",
    password="secret",
    labels=["INBOX"],
    imap_host="imap.example.com",
    imap_port=993,
)

BRIDGE_ACCOUNT = Account(
    provider="protonmail-bridge",
    user="test@proton.me",
    password="secret",
    labels=["INBOX"],
    imap_host="127.0.0.1",
    imap_port=1143,
    imap_starttls=True,
)


def test_no_account_lists_available(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["list-folders"])
    monkeypatch.setattr(
        "sync.folders.load_accounts_or_env",
        lambda: {"test": GMAIL_ACCOUNT},
    )
    main()
    out = capsys.readouterr().out
    assert "test" in out
    assert "test@example.com" in out


def test_unknown_account_exits(monkeypatch):
    monkeypatch.setattr("sys.argv", ["list-folders", "nope"])
    monkeypatch.setattr(
        "sync.folders.load_accounts_or_env",
        lambda: {"test": GMAIL_ACCOUNT},
    )
    with pytest.raises(SystemExit, match="Unknown account"):
        main()


@patch("sync.folders.IMAPClient")
def test_lists_folders(mock_imap_cls, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["list-folders", "test"])
    monkeypatch.setattr(
        "sync.folders.load_accounts_or_env",
        lambda: {"test": GMAIL_ACCOUNT},
    )
    monkeypatch.setattr("sync.folders.resolve_password", lambda _acct: "secret")

    mock_imap = MagicMock()
    mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
    mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_imap.list_folders.return_value = [
        ([b"\\Marked"], b"/", "INBOX"),
        ([b"\\Sent"], b"/", "Sent"),
        ([b"\\Drafts"], b"/", "Drafts"),
    ]

    main()
    out = capsys.readouterr().out
    assert "INBOX" in out
    assert "Sent" in out
    assert "Drafts" in out


@patch("sync.folders.IMAPClient")
def test_starttls_for_bridge(mock_imap_cls, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["list-folders", "bridge"])
    monkeypatch.setattr(
        "sync.folders.load_accounts_or_env",
        lambda: {"bridge": BRIDGE_ACCOUNT},
    )
    monkeypatch.setattr("sync.folders.resolve_password", lambda _acct: "secret")

    mock_imap = MagicMock()
    mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
    mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_imap.list_folders.return_value = [
        ([b"\\Marked"], b"/", "INBOX"),
    ]

    main()

    # Should have called starttls
    mock_imap.starttls.assert_called_once()
    # Should connect without SSL (starttls upgrades after)
    mock_imap_cls.assert_called_once()
    _, kwargs = mock_imap_cls.call_args
    assert kwargs["ssl"] is False
