"""Tests for collab config parser (load/save collaborators.toml)."""

from pathlib import Path
from unittest.mock import patch

from collab import Collaborator, collab_dir, load_collaborators, save_collaborators


def test_load_missing_file(tmp_path):
    result = load_collaborators(tmp_path / "nonexistent.toml")
    assert result == {}


def test_load_empty_file(tmp_path):
    p = tmp_path / "collaborators.toml"
    p.write_text("", encoding="utf-8")
    result = load_collaborators(p)
    assert result == {}


def test_load_single_collaborator(tmp_path):
    p = tmp_path / "collaborators.toml"
    p.write_text(
        '[alex-gh]\nlabels = ["for-alex"]\nname = "Alex"\n',
        encoding="utf-8",
    )
    result = load_collaborators(p)
    assert "alex-gh" in result
    c = result["alex-gh"]
    assert c.labels == ["for-alex"]
    assert c.github_user == "alex-gh"
    assert c.name == "Alex"


def test_load_multiple_collaborators(tmp_path):
    p = tmp_path / "collaborators.toml"
    p.write_text(
        '[alex-gh]\nlabels = ["for-alex"]\n'
        'name = "Alex"\n\n'
        '[bot-agent]\nlabels = ["for-bot", "triage"]\n',
        encoding="utf-8",
    )
    result = load_collaborators(p)
    assert len(result) == 2
    assert result["bot-agent"].labels == ["for-bot", "triage"]
    assert result["bot-agent"].github_user == "bot-agent"
    assert result["bot-agent"].name == ""


def test_save_round_trip(tmp_path):
    p = tmp_path / "collaborators.toml"
    collabs = {
        "alex-gh": Collaborator(
            labels=["for-alex"],
            github_user="alex-gh",
            name="Alex",
            repo="org/to-alex-gh",
        ),
        "bot-agent": Collaborator(
            labels=["for-bot", "triage"],
            github_user="bot-agent",
            repo="org/to-bot-agent",
        ),
    }
    save_collaborators(collabs, p)

    reloaded = load_collaborators(p)
    assert len(reloaded) == 2
    assert reloaded["alex-gh"].labels == ["for-alex"]
    assert reloaded["alex-gh"].github_user == "alex-gh"
    assert reloaded["alex-gh"].name == "Alex"
    assert reloaded["bot-agent"].labels == ["for-bot", "triage"]
    assert reloaded["bot-agent"].name == ""


def test_save_overwrites(tmp_path):
    p = tmp_path / "collaborators.toml"
    save_collaborators(
        {"a-gh": Collaborator(labels=["x"], github_user="a-gh", repo="r/to-a-gh")}, p
    )
    save_collaborators(
        {"b-gh": Collaborator(labels=["y"], github_user="b-gh", repo="r/to-b-gh")}, p
    )
    result = load_collaborators(p)
    assert "a-gh" not in result
    assert "b-gh" in result


def test_collab_dir():
    c = Collaborator(labels=["x"], github_user="Alex-GH")
    assert collab_dir(c) == Path("correspondence/for/alex-gh")


def test_auto_repo_derivation(tmp_path):
    """repo is auto-derived from owner config when not set in TOML."""
    p = tmp_path / "collaborators.toml"
    p.write_text(
        '[alex-gh]\nlabels = ["for-alex"]\n',
        encoding="utf-8",
    )

    from accounts import OwnerConfig

    mock_owner = OwnerConfig(github_user="btakita", name="Brian")
    with patch("accounts.load_owner", return_value=mock_owner):
        result = load_collaborators(p)

    assert result["alex-gh"].repo == "btakita/to-alex-gh"
