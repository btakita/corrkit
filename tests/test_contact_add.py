"""Tests for contact-add command."""

import subprocess

from contact import Contact, load_contacts, save_contacts
from contact.add import _generate_agents_md, main


def test_generate_agents_md_includes_name():
    md = _generate_agents_md("alex")
    assert "# Contact: alex" in md
    assert "drafting emails to or about alex" in md


def test_generate_agents_md_different_names():
    for name in ["dana", "research-team", "bot"]:
        md = _generate_agents_md(name)
        assert f"# Contact: {name}" in md


def test_add_creates_directory_and_config(tmp_path, monkeypatch):
    """contact-add scaffolds directory and writes config entry."""
    config_path = tmp_path / "contacts.toml"
    config_path.write_text("", encoding="utf-8")
    contacts_dir = tmp_path / "correspondence" / "contacts"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("resolve.contacts_dir", lambda: contacts_dir)
    monkeypatch.setattr("resolve.contacts_toml", lambda: config_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "contact-add",
            "alex",
            "--email",
            "alex@example.com",
            "--label",
            "correspondence",
        ],
    )

    main()

    # Check directory was created
    assert (contacts_dir / "alex" / "AGENTS.md").exists()
    assert (contacts_dir / "alex" / "CLAUDE.md").is_symlink()
    claude_md = (contacts_dir / "alex" / "CLAUDE.md").resolve()
    agents_md = (contacts_dir / "alex" / "AGENTS.md").resolve()
    assert claude_md == agents_md

    # Check config was updated
    contacts = load_contacts(config_path)
    assert "alex" in contacts
    assert contacts["alex"].emails == ["alex@example.com"]
    assert contacts["alex"].labels == ["correspondence"]


def test_add_multiple_emails(tmp_path, monkeypatch):
    """Repeating --email stores all emails."""
    config_path = tmp_path / "contacts.toml"
    config_path.write_text("", encoding="utf-8")
    contacts_dir = tmp_path / "correspondence" / "contacts"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("resolve.contacts_dir", lambda: contacts_dir)
    monkeypatch.setattr("resolve.contacts_toml", lambda: config_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "contact-add",
            "alex",
            "--email",
            "alex@example.com",
            "--email",
            "alex@work.com",
        ],
    )

    main()

    contacts = load_contacts(config_path)
    assert contacts["alex"].emails == ["alex@example.com", "alex@work.com"]


def test_add_with_account(tmp_path, monkeypatch):
    """--account flag is stored in config."""
    config_path = tmp_path / "contacts.toml"
    config_path.write_text("", encoding="utf-8")
    contacts_dir = tmp_path / "correspondence" / "contacts"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("resolve.contacts_dir", lambda: contacts_dir)
    monkeypatch.setattr("resolve.contacts_toml", lambda: config_path)
    monkeypatch.setattr(
        "sys.argv",
        ["contact-add", "alex", "--email", "alex@example.com", "--account", "personal"],
    )

    main()

    contacts = load_contacts(config_path)
    assert contacts["alex"].account == "personal"


def test_add_exits_if_already_exists(tmp_path, monkeypatch):
    """contact-add rejects duplicate contact names."""
    config_path = tmp_path / "contacts.toml"
    save_contacts(
        {"alex": Contact(emails=["alex@example.com"])},
        config_path,
    )
    contacts_dir = tmp_path / "correspondence" / "contacts"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("resolve.contacts_dir", lambda: contacts_dir)
    monkeypatch.setattr("resolve.contacts_toml", lambda: config_path)
    monkeypatch.setattr(
        "sys.argv",
        ["contact-add", "alex", "--email", "alex@example.com"],
    )

    import pytest

    with pytest.raises(SystemExit):
        main()


def test_add_exits_if_directory_exists(tmp_path, monkeypatch):
    """contact-add rejects if contacts/{name} directory already exists."""
    config_path = tmp_path / "contacts.toml"
    config_path.write_text("", encoding="utf-8")
    contacts_dir = tmp_path / "correspondence" / "contacts"
    (contacts_dir / "alex").mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("resolve.contacts_dir", lambda: contacts_dir)
    monkeypatch.setattr("resolve.contacts_toml", lambda: config_path)
    monkeypatch.setattr(
        "sys.argv",
        ["contact-add", "alex", "--email", "alex@example.com"],
    )

    import pytest

    with pytest.raises(SystemExit):
        main()


def test_agents_md_has_template_sections():
    """AGENTS.md includes all expected template sections."""
    md = _generate_agents_md("alex")
    assert "## Relationship" in md
    assert "## Tone" in md
    assert "## Topics" in md
    assert "## Notes" in md


def test_add_with_label_and_account_updates_accounts_toml(tmp_path, monkeypatch):
    """contact-add with --label and --account adds label to accounts.toml."""
    contacts_config = tmp_path / "contacts.toml"
    contacts_config.write_text("", encoding="utf-8")
    contacts_dir = tmp_path / "correspondence" / "contacts"

    accounts_config = tmp_path / "accounts.toml"
    accounts_config.write_text(
        '[accounts.personal]\nprovider = "gmail"\n'
        'user = "user@gmail.com"\nlabels = ["correspondence"]\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("resolve.contacts_dir", lambda: contacts_dir)
    monkeypatch.setattr("resolve.contacts_toml", lambda: contacts_config)
    monkeypatch.setattr("resolve.accounts_toml", lambda: accounts_config)
    monkeypatch.setattr(
        "sys.argv",
        [
            "contact-add",
            "alex",
            "--email",
            "alex@example.com",
            "--label",
            "for-alex",
            "--account",
            "personal",
        ],
    )

    main()

    from accounts import load_accounts

    accounts = load_accounts(accounts_config)
    assert "for-alex" in accounts["personal"].labels


def test_contact_add_listed_in_help():
    """corrkit --help includes the contact-add command."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "contact-add" in result.stdout
