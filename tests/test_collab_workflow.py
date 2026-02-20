"""End-to-end tests for the collaborator workflow (sync routing, draft round-trip,
scripts, collab-sync)."""

import subprocess
from pathlib import Path

from collab import Collaborator, save_collaborators
from collab.add import TEMPLATES_DIR, _generate_agents_md
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

    # Make TEMPLATES_DIR point to a temp dir so script sync doesn't fail
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "find_unanswered.py").write_text("# stub", encoding="utf-8")
    (templates / "validate_draft.py").write_text("# stub", encoding="utf-8")
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
# 4. Script validation: find_unanswered.py
# ---------------------------------------------------------------------------


def test_find_unanswered_script(tmp_path):
    """find_unanswered.py finds threads where last sender isn't Brian."""
    conversations = tmp_path / "conversations" / "for-alex"
    conversations.mkdir(parents=True)

    # Thread where last message is from someone else -> unanswered
    (conversations / "2025-02-10-hello.md").write_text(
        "# Hello\n\n"
        "**Label**: for-alex\n"
        "**Thread ID**: t1\n"
        "**Last updated**: 2025-02-10\n\n"
        "---\n\n"
        "## Brian \u2014 Mon, 10 Feb 2025 10:00:00 +0000\n\n"
        "Hi there.\n\n"
        "---\n\n"
        "## Alice \u2014 Mon, 10 Feb 2025 11:00:00 +0000\n\n"
        "Hey Brian!\n",
        encoding="utf-8",
    )

    # Thread where last message is from Brian -> answered
    (conversations / "2025-02-10-update.md").write_text(
        "# Update\n\n"
        "**Label**: for-alex\n"
        "**Thread ID**: t2\n"
        "**Last updated**: 2025-02-10\n\n"
        "---\n\n"
        "## Alice \u2014 Mon, 10 Feb 2025 09:00:00 +0000\n\n"
        "Question?\n\n"
        "---\n\n"
        "## Brian \u2014 Mon, 10 Feb 2025 12:00:00 +0000\n\n"
        "Answer.\n",
        encoding="utf-8",
    )

    script = TEMPLATES_DIR / "find_unanswered.py"
    result = subprocess.run(
        ["python", str(script)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "hello" in result.stdout.lower()
    assert "update" not in result.stdout.lower()


def test_find_unanswered_no_threads(tmp_path):
    """find_unanswered.py handles empty conversations."""
    conversations = tmp_path / "conversations"
    conversations.mkdir()

    script = TEMPLATES_DIR / "find_unanswered.py"
    result = subprocess.run(
        ["python", str(script)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "no unanswered" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 5. Script validation: validate_draft.py
# ---------------------------------------------------------------------------


def test_validate_draft_valid(tmp_path):
    """validate_draft.py passes a valid draft."""
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Test Subject\n\n"
        "**To**: a@b.com\n"
        "**Status**: review\n"
        "**Author**: alex\n\n"
        "---\n\n"
        "Body text.\n",
        encoding="utf-8",
    )

    script = TEMPLATES_DIR / "validate_draft.py"
    result = subprocess.run(
        ["python", str(script), str(draft)],
        capture_output=True,
        text=True,
    )

    assert "OK" in result.stdout


def test_validate_draft_missing_to(tmp_path):
    """validate_draft.py detects missing **To** field."""
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Test Subject\n\n"
        "**Status**: review\n"
        "**Author**: alex\n\n"
        "---\n\n"
        "Body text.\n",
        encoding="utf-8",
    )

    script = TEMPLATES_DIR / "validate_draft.py"
    result = subprocess.run(
        ["python", str(script), str(draft)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "To" in result.stdout


def test_validate_draft_missing_separator(tmp_path):
    """validate_draft.py detects missing --- separator."""
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Test Subject\n\n"
        "**To**: a@b.com\n"
        "**Status**: review\n\n"
        "Body text.\n",
        encoding="utf-8",
    )

    script = TEMPLATES_DIR / "validate_draft.py"
    result = subprocess.run(
        ["python", str(script), str(draft)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "---" in result.stdout


def test_validate_draft_warns_on_draft_status(tmp_path):
    """validate_draft.py warns when status is still 'draft'."""
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Test Subject\n\n"
        "**To**: a@b.com\n"
        "**Status**: draft\n"
        "**Author**: alex\n\n"
        "---\n\n"
        "Body text.\n",
        encoding="utf-8",
    )

    script = TEMPLATES_DIR / "validate_draft.py"
    result = subprocess.run(
        ["python", str(script), str(draft)],
        capture_output=True,
        text=True,
    )

    assert "Warning" in result.stdout
    assert "review" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 6. AGENTS.md template includes all sections
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

    # Script references
    assert "find_unanswered.py" in md
    assert "validate_draft.py" in md


# ---------------------------------------------------------------------------
# 7. collab-sync syncs scripts
# ---------------------------------------------------------------------------


def test_collab_sync_copies_scripts(tmp_path, monkeypatch, capsys):
    """_sync_one copies scripts from templates to shared/{name}/scripts/."""
    from collab.sync import _sync_one

    shared = tmp_path / "shared" / "alex"
    shared.mkdir(parents=True)
    (shared / "voice.md").write_text("# Voice\n", encoding="utf-8")

    monkeypatch.setattr("collab.sync.SHARED_DIR", tmp_path / "shared")
    root_voice = tmp_path / "voice.md"
    root_voice.write_text("# Voice\n", encoding="utf-8")
    monkeypatch.setattr("collab.sync.VOICE_FILE", root_voice)

    # Set up templates
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "find_unanswered.py").write_text("# find script v2", encoding="utf-8")
    (templates / "validate_draft.py").write_text(
        "# validate script v2", encoding="utf-8"
    )
    (templates / "notify.yml").write_text("name: notify v2", encoding="utf-8")
    monkeypatch.setattr("collab.sync.TEMPLATES_DIR", templates)

    def fake_run(cmd, **kw):
        if "status" in cmd and "--porcelain" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="M file\n", stderr="")
        if "pull" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Already up to date.\n", stderr=""
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("collab.sync.subprocess.run", fake_run)

    _sync_one("alex")

    # Verify scripts were copied
    assert (shared / "scripts" / "find_unanswered.py").exists()
    assert (shared / "scripts" / "validate_draft.py").exists()
    assert (shared / ".github" / "workflows" / "notify.yml").exists()

    assert (shared / "scripts" / "find_unanswered.py").read_text() == "# find script v2"

    out = capsys.readouterr().out
    assert "Updated scripts/find_unanswered.py" in out
    assert "Updated scripts/validate_draft.py" in out
    assert "Updated .github/workflows/notify.yml" in out
