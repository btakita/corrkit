"""Tests for collab-sync and collab-status commands."""

import subprocess

from collab import Collaborator, save_collaborators
from collab.sync import _submodule_status, _sync_one, main


def _ok(stdout="", stderr=""):
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr=stderr)


def _fail(stderr="error"):
    return subprocess.CompletedProcess([], 1, stdout="", stderr=stderr)


def test_sync_one_skips_missing_submodule(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "nobody": Collaborator(
                labels=["x"], github_user="nobody", repo="o/to-nobody"
            )
        },
        config_path,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _sync_one("nobody")
    out = capsys.readouterr().out
    assert "not found" in out


def test_sync_one_pulls_and_pushes(tmp_path, monkeypatch, capsys):
    """Full sync: pull, copy voice.md, stage, commit, push."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["for-alex"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)

    sub = tmp_path / "correspondence" / "for" / "alex-gh"
    sub.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    # Create voice files -- root newer than sub
    sub_voice = sub / "voice.md"
    sub_voice.write_text("# Voice v1\n", encoding="utf-8")
    root_voice = tmp_path / "voice.md"
    root_voice.write_text("# Voice v2\n", encoding="utf-8")
    monkeypatch.setattr("collab.sync.VOICE_FILE", root_voice)

    # Templates for workflow sync
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "notify.yml").write_text("# stub", encoding="utf-8")
    monkeypatch.setattr("collab.sync.TEMPLATES_DIR", templates)

    cmds_run: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds_run.append(cmd)
        if "status" in cmd and "--porcelain" in cmd:
            return _ok(stdout="M voice.md\n")
        if "pull" in cmd:
            return _ok(stdout="Updating abc..def\n")
        return _ok()

    monkeypatch.setattr("collab.sync.subprocess.run", fake_run)

    _sync_one("alex-gh")

    out = capsys.readouterr().out
    assert "Syncing alex-gh" in out
    assert "Pulled changes" in out
    assert "Updated voice.md" in out

    # Verify git commands were issued
    cmd_strs = [" ".join(c) for c in cmds_run]
    assert any("pull" in s for s in cmd_strs)
    assert any("add -A" in s for s in cmd_strs)
    assert any("commit" in s for s in cmd_strs)
    assert any("push" in s for s in cmd_strs)


def test_sync_one_no_changes(tmp_path, monkeypatch, capsys):
    """No local changes means no commit/push."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["for-alex"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)

    sub = tmp_path / "correspondence" / "for" / "alex-gh"
    sub.mkdir(parents=True)
    (sub / "voice.md").write_text("# Voice\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    root_voice = tmp_path / "voice.md"
    root_voice.write_text("# Voice\n", encoding="utf-8")
    monkeypatch.setattr("collab.sync.VOICE_FILE", root_voice)

    # Templates for workflow sync
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "notify.yml").write_text("# stub", encoding="utf-8")
    monkeypatch.setattr("collab.sync.TEMPLATES_DIR", templates)

    cmds_run: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds_run.append(cmd)
        if "status" in cmd and "--porcelain" in cmd:
            return _ok(stdout="")  # no changes
        if "pull" in cmd:
            return _ok(stdout="Already up to date.\n")
        return _ok()

    monkeypatch.setattr("collab.sync.subprocess.run", fake_run)

    _sync_one("alex-gh")

    out = capsys.readouterr().out
    assert "No local changes to push" in out
    cmd_strs = [" ".join(c) for c in cmds_run]
    assert not any("commit" in s for s in cmd_strs)


def test_submodule_status_up_to_date(tmp_path, monkeypatch, capsys):
    sub = tmp_path / "sub"
    sub.mkdir()

    def fake_run(cmd, **kw):
        if "rev-list" in cmd:
            return _ok(stdout="0\n")
        return _ok()

    monkeypatch.setattr("collab.sync.subprocess.run", fake_run)
    _submodule_status("alex-gh", sub)

    out = capsys.readouterr().out
    assert "up to date" in out


def test_submodule_status_incoming(tmp_path, monkeypatch, capsys):
    sub = tmp_path / "sub"
    sub.mkdir()

    def fake_run(cmd, **kw):
        if "rev-list" in cmd and "HEAD..@{u}" in cmd:
            return _ok(stdout="3\n")
        if "rev-list" in cmd:
            return _ok(stdout="0\n")
        return _ok()

    monkeypatch.setattr("collab.sync.subprocess.run", fake_run)
    _submodule_status("alex-gh", sub)

    out = capsys.readouterr().out
    assert "3 incoming" in out


def test_main_status_mode(tmp_path, monkeypatch, capsys):
    """collab-sync --status prints status for each collaborator."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["for-alex"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    sub = tmp_path / "correspondence" / "for" / "alex-gh"
    sub.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("sys.argv", ["collab-sync", "--status"])

    def fake_run(cmd, **kw):
        if "rev-list" in cmd:
            return _ok(stdout="0\n")
        return _ok()

    monkeypatch.setattr("collab.sync.subprocess.run", fake_run)

    main()

    out = capsys.readouterr().out
    assert "alex-gh" in out


def test_main_unknown_collaborator(tmp_path, monkeypatch):
    """collab-sync with unknown name exits."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["x"], github_user="alex-gh", repo="o/to-alex-gh"
            )
        },
        config_path,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("sys.argv", ["collab-sync", "nobody"])

    import pytest

    with pytest.raises(SystemExit):
        main()
