"""Tests for collab config parser (load/save collaborators.toml)."""

from collab import Collaborator, load_collaborators, save_collaborators


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
        '[alex]\nlabels = ["for-alex"]\n'
        'repo = "org/correspondence-shared-alex"\n'
        'github_user = "alex-gh"\n',
        encoding="utf-8",
    )
    result = load_collaborators(p)
    assert "alex" in result
    c = result["alex"]
    assert c.labels == ["for-alex"]
    assert c.repo == "org/correspondence-shared-alex"
    assert c.github_user == "alex-gh"


def test_load_multiple_collaborators(tmp_path):
    p = tmp_path / "collaborators.toml"
    p.write_text(
        '[alex]\nlabels = ["for-alex"]\n'
        'repo = "org/shared-alex"\n'
        'github_user = "alex-gh"\n\n'
        '[bot]\nlabels = ["for-bot", "triage"]\n'
        'repo = "org/shared-bot"\n',
        encoding="utf-8",
    )
    result = load_collaborators(p)
    assert len(result) == 2
    assert result["bot"].labels == ["for-bot", "triage"]
    assert result["bot"].github_user == ""


def test_save_round_trip(tmp_path):
    p = tmp_path / "collaborators.toml"
    collabs = {
        "alex": Collaborator(
            labels=["for-alex"],
            repo="org/shared-alex",
            github_user="alex-gh",
        ),
        "bot": Collaborator(
            labels=["for-bot", "triage"],
            repo="org/shared-bot",
        ),
    }
    save_collaborators(collabs, p)

    reloaded = load_collaborators(p)
    assert len(reloaded) == 2
    assert reloaded["alex"].labels == ["for-alex"]
    assert reloaded["alex"].github_user == "alex-gh"
    assert reloaded["bot"].labels == ["for-bot", "triage"]
    assert reloaded["bot"].github_user == ""


def test_save_overwrites(tmp_path):
    p = tmp_path / "collaborators.toml"
    save_collaborators({"a": Collaborator(labels=["x"], repo="r/a")}, p)
    save_collaborators({"b": Collaborator(labels=["y"], repo="r/b")}, p)
    result = load_collaborators(p)
    assert "a" not in result
    assert "b" in result
