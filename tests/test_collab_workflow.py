"""End-to-end tests for the collaborator workflow (sync routing, draft round-trip,
corrkit commands, collab-sync)."""

import subprocess
from pathlib import Path

from collab import Collaborator, save_collaborators
from collab.add import _generate_agents_md
from draft.push import parse_draft
from sync.imap import _build_label_routes, _merge_message_to_file
from sync.types import Message

# ---------------------------------------------------------------------------
# 1. Sync routes to shared/
# ---------------------------------------------------------------------------


def test_sync_routes_to_shared_dir(tmp_path, monkeypatch):
    """Messages for a collaborator label land in shared/{name}/conversations/."""
    config = tmp_path / "collaborators.toml"
    save_collaborators(
        {"alex": Collaborator(labels=["for-alex"], repo="o/shared-alex")},
        config,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config)

    routes = _build_label_routes()
    assert "for-alex" in routes
    assert routes["for-alex"] == Path("shared/alex/conversations/for-alex")

    # Simulate merge to the routed directory
    out_dir = tmp_path / routes["for-alex"]
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello Alex",
        body="Hi there.",
    )
    _merge_message_to_file(out_dir, "for-alex", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "# Hello Alex" in content
    assert "Alice <alice@example.com>" in content


# ---------------------------------------------------------------------------
# 2. collab-sync stages and commits conversations
# ---------------------------------------------------------------------------


def test_collab_sync_stages_and_commits(tmp_path, monkeypatch, capsys):
    """_sync_one stages, commits, and pushes changes in shared/{name}/."""
    from collab.sync import _sync_one

    shared = tmp_path / "shared" / "alex"
    shared.mkdir(parents=True)
    (shared / "voice.md").write_text("# Voice\n", encoding="utf-8")

    monkeypatch.setattr("collab.sync.SHARED_DIR", tmp_path / "shared")
    root_voice = tmp_path / "voice.md"
    root_voice.write_text("# Voice\n", encoding="utf-8")
    monkeypatch.setattr("collab.sync.VOICE_FILE", root_voice)

    # Make TEMPLATES_DIR point to a temp dir so workflow sync doesn't fail
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "notify.yml").write_text("# stub", encoding="utf-8")
    monkeypatch.setattr("collab.sync.TEMPLATES_DIR", templates)

    cmds_run: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds_run.append(cmd)
        if "status" in cmd and "--porcelain" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="M conv.md\n", stderr="")
        if "pull" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Already up to date.\n", stderr=""
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.sync.subprocess.run", fake_run)

    _sync_one("alex")

    cmd_strs = [" ".join(c) for c in cmds_run]
    assert any("add -A" in s for s in cmd_strs)
    assert any("commit" in s for s in cmd_strs)
    assert any("push" in s for s in cmd_strs)


# ---------------------------------------------------------------------------
# 3. Draft round-trip: create draft, parse it
# ---------------------------------------------------------------------------

ALEX_DRAFT = """\
# Re: Project Update

**To**: bob@example.com
**CC**: carol@example.com
**Status**: review
**Author**: alex
**In-Reply-To**: <msg-456@mail.example.com>

---

Thanks for the update. Here are my thoughts on the next steps.
"""


def test_draft_round_trip(tmp_path):
    """A draft in shared/{name}/drafts/ parses correctly via parse_draft."""
    draft_dir = tmp_path / "shared" / "alex" / "drafts"
    draft_dir.mkdir(parents=True)
    draft_path = draft_dir / "2026-02-19-project-update.md"
    draft_path.write_text(ALEX_DRAFT, encoding="utf-8")

    meta, subject, body = parse_draft(draft_path)

    assert subject == "Re: Project Update"
    assert meta["To"] == "bob@example.com"
    assert meta["CC"] == "carol@example.com"
    assert meta["Status"] == "review"
    assert meta["Author"] == "alex"
    assert meta["In-Reply-To"] == "<msg-456@mail.example.com>"
    assert "next steps" in body


def test_draft_with_account_field(tmp_path):
    """Draft with Account field parses correctly."""
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Test\n\n"
        "**To**: a@b.com\n"
        "**Status**: review\n"
        "**Author**: alex\n"
        "**Account**: personal\n\n"
        "---\n\n"
        "Body\n",
        encoding="utf-8",
    )

    meta, subject, body = parse_draft(draft)
    assert meta["Account"] == "personal"
    assert subject == "Test"


# ---------------------------------------------------------------------------
# 4. AGENTS.md template includes all sections
# ---------------------------------------------------------------------------


def test_agents_md_template_completeness():
    """Expanded AGENTS.md template includes all required sections."""
    md = _generate_agents_md("alex")

    # Core sections
    assert "## Workflow" in md
    assert "## Conversation format" in md
    assert "## Finding unanswered threads" in md
    assert "## Drafting a reply" in md
    assert "### Status flow" in md
    assert "## Voice guidelines" in md

    # Draft format fields
    assert "**To**" in md
    assert "**CC**" in md
    assert "**Status**" in md
    assert "**Author**: alex" in md
    assert "**Account**" in md
    assert "**From**" in md
    assert "**In-Reply-To**" in md

    # Filename convention
    assert "YYYY-MM-DD-slug.md" in md

    # Git workflow
    assert "git pull" in md
    assert "git push" in md

    # Commands reference uvx corrkit, not scripts/
    assert "uvx corrkit find-unanswered" in md
    assert "uvx corrkit validate-draft" in md


# ---------------------------------------------------------------------------
# 5. corrkit find-unanswered and validate-draft via CLI
# ---------------------------------------------------------------------------


def test_find_unanswered_via_corrkit():
    """corrkit find-unanswered --help exits 0."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "find-unanswered", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "reply" in result.stdout.lower()


def test_validate_draft_via_corrkit():
    """corrkit validate-draft --help exits 0."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "validate-draft", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "draft" in result.stdout.lower()
