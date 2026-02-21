"""Tests for 'corrkit init' command."""

import tomllib

import pytest

import app_config
from init import main


@pytest.fixture(autouse=True)
def _isolate_app_config(tmp_path, monkeypatch):
    """Isolate app_config to a temp directory so tests don't write to real config."""
    config_dir = tmp_path / "app-config"
    config_dir.mkdir()
    monkeypatch.setattr(app_config, "app_config_dir", lambda: config_dir)


def test_init_creates_directory_structure(tmp_path, monkeypatch):
    """init creates conversations/, drafts/, contacts/ with .gitkeep."""
    data_dir = tmp_path / "correspondence"
    monkeypatch.setattr(
        "sys.argv",
        ["init", "--user", "test@example.com", "--data-dir", str(data_dir)],
    )

    main()

    for sub in ("conversations", "drafts", "contacts"):
        assert (data_dir / sub).is_dir()
        assert (data_dir / sub / ".gitkeep").exists()


def test_init_creates_accounts_toml(tmp_path, monkeypatch):
    """init generates valid accounts.toml with correct provider/user/labels."""
    data_dir = tmp_path / "correspondence"
    monkeypatch.setattr(
        "sys.argv",
        [
            "init",
            "--user",
            "test@gmail.com",
            "--data-dir",
            str(data_dir),
            "--provider",
            "gmail",
            "--labels",
            "inbox,sent",
            "--github-user",
            "testuser",
            "--name",
            "Test User",
        ],
    )

    main()

    accounts_path = data_dir / "accounts.toml"
    assert accounts_path.exists()

    with open(accounts_path, "rb") as f:
        raw = tomllib.load(f)

    assert raw["owner"]["github_user"] == "testuser"
    assert raw["owner"]["name"] == "Test User"
    assert raw["accounts"]["default"]["provider"] == "gmail"
    assert raw["accounts"]["default"]["user"] == "test@gmail.com"
    assert raw["accounts"]["default"]["labels"] == ["inbox", "sent"]
    assert raw["accounts"]["default"]["default"] is True


def test_init_creates_empty_config_files(tmp_path, monkeypatch):
    """init creates empty collaborators.toml and contacts.toml."""
    data_dir = tmp_path / "correspondence"
    monkeypatch.setattr(
        "sys.argv",
        ["init", "--user", "test@example.com", "--data-dir", str(data_dir)],
    )

    main()

    assert (data_dir / "collaborators.toml").exists()
    assert (data_dir / "contacts.toml").exists()


def test_init_force_overwrites(tmp_path, monkeypatch):
    """--force overwrites existing accounts.toml."""
    data_dir = tmp_path / "correspondence"
    data_dir.mkdir(parents=True)
    accounts = data_dir / "accounts.toml"
    accounts.write_text("old content", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "init",
            "--user",
            "new@example.com",
            "--data-dir",
            str(data_dir),
            "--force",
        ],
    )

    main()

    content = accounts.read_text(encoding="utf-8")
    assert "new@example.com" in content
    assert "old content" not in content


def test_init_without_force_exits_if_exists(tmp_path, monkeypatch):
    """Without --force, init exits 1 if accounts.toml already exists."""
    data_dir = tmp_path / "correspondence"
    data_dir.mkdir(parents=True)
    (data_dir / "accounts.toml").write_text("existing", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["init", "--user", "test@example.com", "--data-dir", str(data_dir)],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_init_password_cmd_in_toml(tmp_path, monkeypatch):
    """--password-cmd is written to accounts.toml."""
    data_dir = tmp_path / "correspondence"
    monkeypatch.setattr(
        "sys.argv",
        [
            "init",
            "--user",
            "test@example.com",
            "--data-dir",
            str(data_dir),
            "--password-cmd",
            "pass email/test",
        ],
    )

    main()

    with open(data_dir / "accounts.toml", "rb") as f:
        raw = tomllib.load(f)
    assert raw["accounts"]["default"]["password_cmd"] == "pass email/test"


def test_init_protonmail_provider(tmp_path, monkeypatch):
    """init with protonmail-bridge provider works."""
    data_dir = tmp_path / "correspondence"
    monkeypatch.setattr(
        "sys.argv",
        [
            "init",
            "--user",
            "test@pm.me",
            "--data-dir",
            str(data_dir),
            "--provider",
            "protonmail-bridge",
            "--password-cmd",
            "pass email/proton",
        ],
    )

    main()

    with open(data_dir / "accounts.toml", "rb") as f:
        raw = tomllib.load(f)
    assert raw["accounts"]["default"]["provider"] == "protonmail-bridge"


def test_init_registers_space(tmp_path, monkeypatch):
    """init registers the data dir as a space in app config."""
    data_dir = tmp_path / "correspondence"
    monkeypatch.setattr(
        "sys.argv",
        ["init", "--user", "test@example.com", "--data-dir", str(data_dir)],
    )

    main()

    config = app_config.load()
    assert "default" in config["spaces"]
    assert config["spaces"]["default"]["path"] == str(data_dir)
    assert config["default_space"] == "default"


def test_init_custom_space_name(tmp_path, monkeypatch):
    """--space sets a custom space name."""
    data_dir = tmp_path / "correspondence"
    monkeypatch.setattr(
        "sys.argv",
        [
            "init",
            "--user",
            "test@example.com",
            "--data-dir",
            str(data_dir),
            "--space",
            "work",
        ],
    )

    main()

    config = app_config.load()
    assert "work" in config["spaces"]
    assert config["default_space"] == "work"
