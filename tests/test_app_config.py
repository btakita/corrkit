"""Tests for app_config module."""

from pathlib import Path

import pytest

import app_config


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Point app_config_dir to a temp directory for all tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(app_config, "app_config_dir", lambda: config_dir)


def test_load_empty_when_no_file():
    """load() returns {} when config.toml doesn't exist."""
    assert app_config.load() == {}


def test_save_and_load(tmp_path):
    """save() writes config that load() can read back."""
    config = {"default_space": "work", "spaces": {"work": {"path": "/tmp/work"}}}
    app_config.save(config)
    loaded = app_config.load()
    assert loaded == config


def test_add_space_first_sets_default():
    """First space added becomes the default."""
    app_config.add_space("personal", "~/Documents/correspondence")
    config = app_config.load()
    assert config["default_space"] == "personal"
    assert config["spaces"]["personal"]["path"] == "~/Documents/correspondence"


def test_add_space_second_does_not_change_default():
    """Adding a second space doesn't change the default."""
    app_config.add_space("personal", "~/Documents/correspondence")
    app_config.add_space("work", "~/work/correspondence")
    config = app_config.load()
    assert config["default_space"] == "personal"
    assert "work" in config["spaces"]


def test_resolve_space_by_name():
    """resolve_space(name) returns the named space's path."""
    app_config.add_space("work", "~/work/correspondence")
    result = app_config.resolve_space("work")
    assert result == Path("~/work/correspondence").expanduser()


def test_resolve_space_unknown_name():
    """resolve_space(unknown) raises SystemExit."""
    app_config.add_space("work", "~/work/correspondence")
    with pytest.raises(SystemExit):
        app_config.resolve_space("missing")


def test_resolve_space_no_name_uses_default():
    """resolve_space(None) uses default_space."""
    app_config.add_space("personal", "~/Documents/correspondence")
    app_config.add_space("work", "~/work/correspondence")
    result = app_config.resolve_space(None)
    assert result == Path("~/Documents/correspondence").expanduser()


def test_resolve_space_no_name_single_space():
    """resolve_space(None) uses the only space when there's just one."""
    app_config.add_space("personal", "~/Documents/correspondence")
    result = app_config.resolve_space(None)
    assert result == Path("~/Documents/correspondence").expanduser()


def test_resolve_space_no_name_multiple_no_default():
    """resolve_space(None) exits when multiple spaces and no default."""
    config = {
        "spaces": {
            "personal": {"path": "~/Documents/correspondence"},
            "work": {"path": "~/work/correspondence"},
        }
    }
    app_config.save(config)
    with pytest.raises(SystemExit):
        app_config.resolve_space(None)


def test_resolve_space_no_spaces():
    """resolve_space(None) returns None when no spaces configured."""
    assert app_config.resolve_space(None) is None


def test_app_config_path():
    """app_config_path() returns config.toml inside config dir."""
    path = app_config.app_config_path()
    assert path.name == "config.toml"
    assert path.parent == app_config.app_config_dir()


def test_save_creates_parent_dir(tmp_path, monkeypatch):
    """save() creates parent directories if they don't exist."""
    nested = tmp_path / "deep" / "nested" / "config"
    monkeypatch.setattr(app_config, "app_config_dir", lambda: nested)
    app_config.save({"spaces": {}})
    assert app_config.app_config_path().exists()
