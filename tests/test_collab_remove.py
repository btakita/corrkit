"""Tests for 'corrkit for remove' command."""

import subprocess

import pytest

from collab import Collaborator, load_collaborators, save_collaborators
from collab.remove import main


def _ok():
    return subprocess.CompletedProcess([], 0, stdout="", stderr="")


def test_remove_deletes_config_entry(tmp_path, monkeypatch):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["for-alex"],
                repo="o/to-alex-gh",
                github_user="alex-gh",
                name="Alex",
            ),
            "bot-agent": Collaborator(
                labels=["for-bot"],
                repo="o/to-bot-agent",
                github_user="bot-agent",
            ),
        },
        config_path,
    )
    monkeypatch.setattr("resolve.collaborators_toml", lambda: config_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.remove.subprocess.run", lambda cmd, **kw: _ok())
    monkeypatch.setattr("sys.argv", ["for remove", "alex-gh"])

    main()

    result = load_collaborators(config_path)
    assert "alex-gh" not in result
    assert "bot-agent" in result


def test_remove_runs_submodule_deinit(tmp_path, monkeypatch):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["x"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    sub = tmp_path / "correspondence" / "for" / "alex-gh"
    sub.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    cmds: list[list[str]] = []

    def capture(cmd, **kw):
        cmds.append(cmd)
        return _ok()

    monkeypatch.setattr("resolve.collaborators_toml", lambda: config_path)
    monkeypatch.setattr("collab.remove.subprocess.run", capture)
    monkeypatch.setattr("sys.argv", ["for remove", "alex-gh"])

    main()

    cmd_strs = [" ".join(c) for c in cmds]
    assert any("submodule" in s and "deinit" in s for s in cmd_strs)
    assert any("git" in s and "rm" in s for s in cmd_strs)


def test_remove_skips_git_when_no_submodule_dir(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["x"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("resolve.collaborators_toml", lambda: config_path)
    monkeypatch.setattr(
        "collab.remove.subprocess.run",
        lambda cmd, **kw: _ok(),
    )
    monkeypatch.setattr("sys.argv", ["for remove", "alex-gh"])

    main()

    out = capsys.readouterr().out
    assert "not found on disk" in out


def test_remove_unknown_name_exits(tmp_path, monkeypatch):
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setattr("resolve.collaborators_toml", lambda: config_path)
    monkeypatch.setattr("sys.argv", ["for remove", "ghost"])

    with pytest.raises(SystemExit):
        main()


def test_remove_delete_repo_prompts(tmp_path, monkeypatch, capsys):
    """--delete-repo with 'y' input runs gh repo delete."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["x"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    monkeypatch.chdir(tmp_path)

    cmds: list[list[str]] = []

    def capture(cmd, **kw):
        cmds.append(cmd)
        return _ok()

    monkeypatch.setattr("resolve.collaborators_toml", lambda: config_path)
    monkeypatch.setattr("collab.remove.subprocess.run", capture)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    monkeypatch.setattr("sys.argv", ["for remove", "alex-gh", "--delete-repo"])

    main()

    cmd_strs = [" ".join(c) for c in cmds]
    assert any("repo" in s and "delete" in s for s in cmd_strs)


def test_remove_delete_repo_declined(tmp_path, monkeypatch, capsys):
    """--delete-repo with 'n' input skips deletion."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["x"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    monkeypatch.chdir(tmp_path)

    cmds: list[list[str]] = []

    def capture(cmd, **kw):
        cmds.append(cmd)
        return _ok()

    monkeypatch.setattr("resolve.collaborators_toml", lambda: config_path)
    monkeypatch.setattr("collab.remove.subprocess.run", capture)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    monkeypatch.setattr("sys.argv", ["for remove", "alex-gh", "--delete-repo"])

    main()

    cmd_strs = [" ".join(c) for c in cmds]
    assert not any("repo" in s and "delete" in s for s in cmd_strs)
    out = capsys.readouterr().out
    assert "Skipped repo deletion" in out
