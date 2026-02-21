"""Tests for add-label command and add_label_to_account()."""

import subprocess

import pytest

from accounts import add_label_to_account, load_accounts


def _write_accounts_toml(path, text):
    path.write_text(text, encoding="utf-8")


def test_add_label_basic(tmp_path):
    """Adds a label to an existing account."""
    cfg = tmp_path / "accounts.toml"
    _write_accounts_toml(
        cfg,
        """\
[accounts.personal]
provider = "gmail"
user = "user@gmail.com"
labels = ["correspondence"]
""",
    )

    result = add_label_to_account("personal", "for-alex", path=cfg)
    assert result is True

    accounts = load_accounts(cfg)
    assert "for-alex" in accounts["personal"].labels
    assert "correspondence" in accounts["personal"].labels


def test_add_label_already_present(tmp_path):
    """Returns False when label already exists."""
    cfg = tmp_path / "accounts.toml"
    _write_accounts_toml(
        cfg,
        """\
[accounts.personal]
provider = "gmail"
user = "user@gmail.com"
labels = ["correspondence"]
""",
    )

    result = add_label_to_account("personal", "correspondence", path=cfg)
    assert result is False


def test_add_label_empty_labels(tmp_path):
    """Adds a label when the labels list is empty."""
    cfg = tmp_path / "accounts.toml"
    _write_accounts_toml(
        cfg,
        """\
[accounts.personal]
provider = "gmail"
user = "user@gmail.com"
labels = []
""",
    )

    result = add_label_to_account("personal", "inbox", path=cfg)
    assert result is True

    accounts = load_accounts(cfg)
    assert accounts["personal"].labels == ["inbox"]


def test_add_label_preserves_comments(tmp_path):
    """Text-level edit preserves TOML comments."""
    cfg = tmp_path / "accounts.toml"
    _write_accounts_toml(
        cfg,
        """\
# My accounts
[accounts.personal]
provider = "gmail"  # gmail provider
user = "user@gmail.com"
labels = ["correspondence"]
default = true
""",
    )

    add_label_to_account("personal", "for-alex", path=cfg)

    text = cfg.read_text(encoding="utf-8")
    assert "# My accounts" in text
    assert "# gmail provider" in text


def test_add_label_unknown_account(tmp_path):
    """Exits with error for unknown account name."""
    cfg = tmp_path / "accounts.toml"
    _write_accounts_toml(
        cfg,
        """\
[accounts.personal]
provider = "gmail"
user = "user@gmail.com"
labels = ["correspondence"]
""",
    )

    with pytest.raises(SystemExit):
        add_label_to_account("nonexistent", "test", path=cfg)


def test_add_label_multiple_accounts(tmp_path):
    """Only modifies the targeted account."""
    cfg = tmp_path / "accounts.toml"
    _write_accounts_toml(
        cfg,
        """\
[accounts.personal]
provider = "gmail"
user = "user@gmail.com"
labels = ["correspondence"]

[accounts.work]
provider = "imap"
user = "user@work.com"
labels = ["inbox"]
""",
    )

    add_label_to_account("personal", "for-alex", path=cfg)

    accounts = load_accounts(cfg)
    assert "for-alex" in accounts["personal"].labels
    assert accounts["work"].labels == ["inbox"]


def test_add_label_listed_in_help():
    """corrkit --help includes the add-label command."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "add-label" in result.stdout
