"""Tests for 'corrkit for rename' command."""

import subprocess

import pytest

from collab import Collaborator, load_collaborators, save_collaborators
from collab.rename import main


def _ok():
    return subprocess.CompletedProcess([], 0, stdout="", stderr="")


def test_rename_updates_config(tmp_path, monkeypatch):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "old-gh": Collaborator(
                labels=["for-old"],
                repo="o/to-old-gh",
                github_user="old-gh",
                name="Old",
                account="personal",
            )
        },
        config_path,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.rename.subprocess.run", lambda cmd, **kw: _ok())
    monkeypatch.setattr("sys.argv", ["for rename", "old-gh", "new-gh"])

    main()

    result = load_collaborators(config_path)
    assert "old-gh" not in result
    assert "new-gh" in result
    assert result["new-gh"].labels == ["for-old"]
    assert result["new-gh"].name == "Old"
    assert result["new-gh"].account == "personal"


def test_rename_runs_git_mv(tmp_path, monkeypatch):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "old-gh": Collaborator(
                labels=["x"], github_user="old-gh", repo="o/to-old-gh"
            )
        },
        config_path,
    )
    sub = tmp_path / "correspondence" / "for" / "old-gh"
    sub.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    cmds: list[list[str]] = []

    def capture(cmd, **kw):
        cmds.append(cmd)
        return _ok()

    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("collab.rename.subprocess.run", capture)
    monkeypatch.setattr("sys.argv", ["for rename", "old-gh", "new-gh"])

    main()

    cmd_strs = [" ".join(c) for c in cmds]
    assert any(
        "git mv" in s
        and "correspondence/for/old-gh" in s
        and "correspondence/for/new-gh" in s
        for s in cmd_strs
    )


def test_rename_old_not_found_exits(tmp_path, monkeypatch):
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("sys.argv", ["for rename", "ghost", "new-gh"])

    with pytest.raises(SystemExit):
        main()


def test_rename_new_already_exists_exits(tmp_path, monkeypatch):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "old-gh": Collaborator(
                labels=["x"], github_user="old-gh", repo="o/to-old-gh"
            ),
            "new-gh": Collaborator(
                labels=["y"], github_user="new-gh", repo="o/to-new-gh"
            ),
        },
        config_path,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("sys.argv", ["for rename", "old-gh", "new-gh"])

    with pytest.raises(SystemExit):
        main()


def test_rename_skips_git_mv_when_no_dir(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "old-gh": Collaborator(
                labels=["x"], github_user="old-gh", repo="o/to-old-gh"
            )
        },
        config_path,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("collab.rename.subprocess.run", lambda cmd, **kw: _ok())
    monkeypatch.setattr("sys.argv", ["for rename", "old-gh", "new-gh"])

    main()

    out = capsys.readouterr().out
    assert "not found on disk" in out


def test_rename_repo_flag(tmp_path, monkeypatch):
    """--rename-repo runs gh repo rename."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "old-gh": Collaborator(
                labels=["x"], github_user="old-gh", repo="owner/to-old-gh"
            )
        },
        config_path,
    )
    monkeypatch.chdir(tmp_path)

    cmds: list[list[str]] = []

    def capture(cmd, **kw):
        cmds.append(cmd)
        return _ok()

    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("collab.rename.subprocess.run", capture)
    monkeypatch.setattr("sys.argv", ["for rename", "old-gh", "new-gh", "--rename-repo"])

    main()

    cmd_strs = [" ".join(c) for c in cmds]
    assert any("repo" in s and "rename" in s and "to-new-gh" in s for s in cmd_strs)

    result = load_collaborators(config_path)
    assert "to-new-gh" in result["new-gh"].repo
