"""Tests for collab-add command."""

import subprocess

from accounts import OwnerConfig
from collab import Collaborator, load_collaborators, save_collaborators
from collab.add import _generate_agents_md, main

MOCK_OWNER = OwnerConfig(github_user="btakita", name="Brian")


def _patch_owner(monkeypatch):
    monkeypatch.setattr("accounts.load_owner", lambda path=None: MOCK_OWNER)


def test_generate_agents_md_includes_name():
    md = _generate_agents_md("alex")
    assert "**Author**: alex" in md
    assert "Shared Correspondence with Brian" in md
    assert "voice.md" in md


def test_generate_agents_md_custom_owner():
    md = _generate_agents_md("alex", owner_name="Dana")
    assert "Shared Correspondence with Dana" in md


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
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _patch_owner(monkeypatch)

    # Simulate argparse
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "alex-gh", "--label", "for-alex", "--name", "Alex"],
    )

    # Create the submodule dir that git submodule add would create
    def fake_run_with_submodule(cmd, **kw):
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "correspondence" / "for" / "alex-gh").mkdir(
                parents=True, exist_ok=True
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.add.subprocess.run", fake_run_with_submodule)

    main()

    collabs = load_collaborators(config_path)
    assert "alex-gh" in collabs
    assert collabs["alex-gh"].labels == ["for-alex"]
    assert collabs["alex-gh"].repo == "btakita/to-alex-gh"
    assert collabs["alex-gh"].github_user == "alex-gh"
    assert collabs["alex-gh"].name == "Alex"


def test_add_exits_if_already_exists(tmp_path, monkeypatch):
    """collab-add rejects duplicate collaborator names."""
    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["x"], github_user="alex-gh", repo="r/to-alex-gh"
            )
        },
        config_path,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _patch_owner(monkeypatch)
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "alex-gh", "--label", "for-alex"],
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
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _patch_owner(monkeypatch)

    captured_cmds: list[list[str]] = []

    def capture_run(cmd, **kw):
        captured_cmds.append(cmd)
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "correspondence" / "for" / "newuser").mkdir(
                parents=True, exist_ok=True
            )
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
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _patch_owner(monkeypatch)

    captured_cmds: list[list[str]] = []

    def capture_run(cmd, **kw):
        captured_cmds.append(cmd)
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "correspondence" / "for" / "pub").mkdir(
                parents=True, exist_ok=True
            )
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


def test_add_multiple_labels(tmp_path, monkeypatch):
    """Repeating --label stores all labels in the config."""
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")
    voice = tmp_path / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _patch_owner(monkeypatch)

    def fake_run(cmd, **kw):
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "correspondence" / "for" / "dana-gh").mkdir(
                parents=True, exist_ok=True
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.add.subprocess.run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "collab-add",
            "dana-gh",
            "--label",
            "for-dana",
            "--label",
            "project-x",
            "--name",
            "Dana",
        ],
    )

    main()

    collabs = load_collaborators(config_path)
    assert collabs["dana-gh"].labels == ["for-dana", "project-x"]


def test_add_custom_org(tmp_path, monkeypatch):
    """--org overrides the default GitHub org in repo name."""
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")
    voice = tmp_path / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.add.VOICE_FILE", voice)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _patch_owner(monkeypatch)

    captured_cmds: list[list[str]] = []

    def capture_run(cmd, **kw):
        captured_cmds.append(cmd)
        if cmd[0] == "git" and "submodule" in cmd:
            (tmp_path / "correspondence" / "for" / "eve").mkdir(
                parents=True, exist_ok=True
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.add.subprocess.run", capture_run)
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "eve", "--label", "for-eve", "--org", "myorg"],
    )

    main()

    collabs = load_collaborators(config_path)
    assert collabs["eve"].repo == "myorg/to-eve"

    create_cmd = [c for c in captured_cmds if "repo" in c and "create" in c]
    assert "myorg/to-eve" in create_cmd[0]


def test_add_exits_if_directory_exists(tmp_path, monkeypatch):
    """collab-add rejects if for/{gh_user} directory already exists on disk."""
    config_path = tmp_path / "collaborators.toml"
    config_path.write_text("", encoding="utf-8")

    (tmp_path / "correspondence" / "for" / "alex-gh").mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("collab.CONFIG_PATH", config_path)
    _patch_owner(monkeypatch)
    monkeypatch.setattr(
        "sys.argv",
        ["collab-add", "alex-gh", "--label", "for-alex"],
    )

    import pytest

    with pytest.raises(SystemExit):
        main()


def test_collab_add_listed_in_help():
    """corrkit --help includes the collab-add command."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "collab-add" in result.stdout
