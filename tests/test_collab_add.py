"""Tests for collab-add command."""

import subprocess

from collab import Collaborator, load_collaborators, save_collaborators
from collab.add import _generate_agents_md, main


def test_generate_agents_md_includes_name():
    md = _generate_agents_md("alex")
    assert "**Author**: alex" in md
    assert "Shared Correspondence with Brian" in md
    assert "voice.md" in md


def test_generate_agents_md_different_names():
    for name in ["bot-agent", "dana", "research-ai"]:
        md = _generate_agents_md(name)
        assert f"**Author**: {name}" in md


def _fake_run_ok(*args, **kwargs):
    return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")


def test_add_creates_config_entry(tmp_path, monkeypatch):
    """collab-add writes correct entry to collaborators.toml."""
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")
    voice = tmp_path / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.add.SHARED_DIR", tmp_path / "shared")
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr("collab.add.subprocess.run", _fake_run_ok)

    # Simulate argparse
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "alex", "--label", "for-alex", "--github-user", "alex-gh"],
    )

    # Create the submodule dir that git submodule add would create
    def fake_run_with_submodule(cmd, **kw):
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "shared" / "alex").mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.add.subprocess.run", fake_run_with_submodule)

    main()

    collabs = load_collaborators(config_path)
    assert "alex" in collabs
    assert collabs["alex"].labels == ["for-alex"]
    assert collabs["alex"].repo == "btakita/correspondence-shared-alex"
    assert collabs["alex"].github_user == "alex-gh"


def test_add_exits_if_already_exists(tmp_path, monkeypatch):
    """collab-add rejects duplicate collaborator names."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {"alex": Collaborator(labels=["x"], repo="r/x", github_user="")},
        config_path,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "alex", "--label", "for-alex"],
    )

    import pytest

    with pytest.raises(SystemExit):
        main()


def test_add_private_by_default(tmp_path, monkeypatch):
    """Default repo visibility is private."""
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")
    voice = tmp_path / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.add.SHARED_DIR", tmp_path / "shared")
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)

    captured_cmds: list[list[str]] = []

    def capture_run(cmd, **kw):
        captured_cmds.append(cmd)
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "shared" / "newuser").mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.add.subprocess.run", capture_run)
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "newuser", "--label", "for-new"],
    )

    main()

    # Find the gh repo create command
    create_cmd = [c for c in captured_cmds if "repo" in c and "create" in c]
    assert len(create_cmd) == 1
    assert "--private" in create_cmd[0]
    assert "--public" not in create_cmd[0]


def test_add_public_flag(tmp_path, monkeypatch):
    """--public flag creates a public repo."""
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")
    voice = tmp_path / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.add.SHARED_DIR", tmp_path / "shared")
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)

    captured_cmds: list[list[str]] = []

    def capture_run(cmd, **kw):
        captured_cmds.append(cmd)
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "shared" / "pub").mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.add.subprocess.run", capture_run)
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "pub", "--label", "for-pub", "--public"],
    )

    main()

    create_cmd = [c for c in captured_cmds if "repo" in c and "create" in c]
    assert len(create_cmd) == 1
    assert "--public" in create_cmd[0]
