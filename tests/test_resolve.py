"""Tests for path resolution logic."""

from pathlib import Path

import app_config
from resolve import config_dir, data_dir


def _no_spaces(monkeypatch):
    """Patch app_config so resolve_space returns None (no spaces configured)."""
    monkeypatch.setattr(app_config, "resolve_space", lambda _name: None)


def test_data_dir_local_correspondence(tmp_path, monkeypatch):
    """data_dir() returns Path('correspondence') when the dir exists in cwd."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "correspondence").mkdir()
    assert data_dir() == Path("correspondence")


def test_data_dir_env_override(tmp_path, monkeypatch):
    """data_dir() returns CORRKIT_DATA env value when set and no local dir."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CORRKIT_DATA", str(tmp_path / "custom"))
    assert data_dir() == tmp_path / "custom"


def test_data_dir_fallback(tmp_path, monkeypatch):
    """data_dir() returns ~/Documents/correspondence as fallback."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORRKIT_DATA", raising=False)
    _no_spaces(monkeypatch)
    result = data_dir()
    assert result == Path.home() / "Documents" / "correspondence"


def test_config_dir_local(tmp_path, monkeypatch):
    """config_dir() returns Path('.') when local correspondence/ exists."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "correspondence").mkdir()
    assert config_dir() == Path(".")


def test_config_dir_no_local(tmp_path, monkeypatch):
    """config_dir() returns data dir when no local correspondence/."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORRKIT_DATA", raising=False)
    _no_spaces(monkeypatch)
    assert config_dir() == data_dir()


def test_data_dir_env_takes_precedence_over_fallback(tmp_path, monkeypatch):
    """CORRKIT_DATA env takes precedence over ~/Documents fallback."""
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "my-data"
    monkeypatch.setenv("CORRKIT_DATA", str(custom))
    assert data_dir() == custom


def test_local_dir_takes_precedence_over_env(tmp_path, monkeypatch):
    """Local correspondence/ takes precedence over CORRKIT_DATA."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "correspondence").mkdir()
    monkeypatch.setenv("CORRKIT_DATA", str(tmp_path / "other"))
    assert data_dir() == Path("correspondence")


def test_data_dir_app_config_space(tmp_path, monkeypatch):
    """data_dir() uses app config space when no local dir or env var."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORRKIT_DATA", raising=False)
    space_path = tmp_path / "my-space"
    monkeypatch.setattr(app_config, "resolve_space", lambda _name: space_path)
    assert data_dir() == space_path


def test_data_dir_env_takes_precedence_over_app_config(tmp_path, monkeypatch):
    """CORRKIT_DATA takes precedence over app config spaces."""
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / "env-data"
    monkeypatch.setenv("CORRKIT_DATA", str(env_path))
    space_path = tmp_path / "space-data"
    monkeypatch.setattr(app_config, "resolve_space", lambda _name: space_path)
    assert data_dir() == env_path
