"""End-to-end tests for the collaborator workflow (sync routing, draft round-trip,
corrkit commands, for sync)."""

import os
import shutil
import subprocess
from pathlib import Path

from accounts import OwnerConfig
from collab import Collaborator, save_collaborators
from collab.add import _generate_agents_md, _generate_readme_md
from draft.push import parse_draft
from sync.imap import _build_label_routes, _merge_message_to_file
from sync.types import Message

MOCK_OWNER = OwnerConfig(github_user="btakita", name="Brian")

# ---------------------------------------------------------------------------
# 1. Sync routes to for/{gh-user}/
# ---------------------------------------------------------------------------


def test_sync_routes_to_collab_dir(tmp_path, monkeypatch):
    """Messages for a collaborator label land in for/{gh-user}/conversations/."""
    config = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "drafter-gh": Collaborator(
                labels=["for-drafter"],
                github_user="drafter-gh",
                repo="o/to-drafter-gh",
            )
        },
        config,
    )
    monkeypatch.setattr("resolve.collaborators_toml", lambda: config)

    routes = _build_label_routes()
    assert "for-drafter" in routes
    assert routes["for-drafter"] == Path("correspondence/for/drafter-gh/conversations")

    # Simulate merge to the routed directory
    out_dir = tmp_path / routes["for-drafter"]
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello Alex",
        body="Hi there.",
    )
    _merge_message_to_file(out_dir, "for-drafter", "personal", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "# Hello Alex" in content
    assert "Alice <alice@example.com>" in content


# ---------------------------------------------------------------------------
# 2. 'for sync' stages and commits conversations
# ---------------------------------------------------------------------------


def test_collab_sync_stages_and_commits(tmp_path, monkeypatch, capsys):
    """_sync_one stages, commits, and pushes changes in for/{gh-user}/."""
    from collab.sync import _sync_one

    config_path = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "drafter-gh": Collaborator(
                labels=["for-drafter"],
                github_user="drafter-gh",
                repo="o/to-drafter-gh",
            )
        },
        config_path,
    )
    monkeypatch.setattr("resolve.collaborators_toml", lambda: config_path)

    sub = tmp_path / "correspondence" / "for" / "drafter-gh"
    sub.mkdir(parents=True)
    (sub / "voice.md").write_text("# Voice\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    root_voice = tmp_path / "voice.md"
    root_voice.write_text("# Voice\n", encoding="utf-8")
    monkeypatch.setattr("resolve.voice_md", lambda: root_voice)

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

    _sync_one("drafter-gh")

    cmd_strs = [" ".join(c) for c in cmds_run]
    assert any("add -A" in s for s in cmd_strs)
    assert any("commit" in s for s in cmd_strs)
    assert any("push" in s for s in cmd_strs)


# ---------------------------------------------------------------------------
# 3. Draft round-trip: create draft, parse it
# ---------------------------------------------------------------------------

DRAFTER_DRAFT = """\
# Re: Project Update

**To**: bob@example.com
**CC**: carol@example.com
**Status**: review
**Author**: drafter
**In-Reply-To**: <msg-456@mail.example.com>

---

Thanks for the update. Here are my thoughts on the next steps.
"""


def test_draft_round_trip(tmp_path):
    """A draft in for/{gh-user}/drafts/ parses correctly via parse_draft."""
    draft_dir = tmp_path / "correspondence" / "for" / "drafter-gh" / "drafts"
    draft_dir.mkdir(parents=True)
    draft_path = draft_dir / "2026-02-19-project-update.md"
    draft_path.write_text(DRAFTER_DRAFT, encoding="utf-8")

    meta, subject, body = parse_draft(draft_path)

    assert subject == "Re: Project Update"
    assert meta["To"] == "bob@example.com"
    assert meta["CC"] == "carol@example.com"
    assert meta["Status"] == "review"
    assert meta["Author"] == "drafter"
    assert meta["In-Reply-To"] == "<msg-456@mail.example.com>"
    assert "next steps" in body


def test_draft_with_account_field(tmp_path):
    """Draft with Account field parses correctly."""
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Test\n\n"
        "**To**: a@b.com\n"
        "**Status**: review\n"
        "**Author**: drafter\n"
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
    md = _generate_agents_md("drafter")

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
    assert "**Author**: drafter" in md
    assert "**Account**" in md
    assert "**From**" in md
    assert "**In-Reply-To**" in md

    # Filename convention
    assert "YYYY-MM-DD-slug.md" in md

    # Git workflow
    assert "git pull" in md
    assert "git push" in md

    # Commands reference uvx corrkit, not scripts/
    assert "uvx corrkit by find-unanswered" in md
    assert "uvx corrkit by validate-draft" in md


def test_agents_md_uses_owner_name():
    """AGENTS.md template parameterizes owner name."""
    md = _generate_agents_md("drafter", owner_name="Dana")
    assert "Shared Correspondence with Dana" in md
    assert "ready for Dana" in md


# ---------------------------------------------------------------------------
# 5. corrkit find-unanswered and validate-draft via CLI
# ---------------------------------------------------------------------------


def test_find_unanswered_via_corrkit():
    """corrkit by find-unanswered --help exits 0."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "by", "find-unanswered", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "reply" in result.stdout.lower()


def test_validate_draft_via_corrkit():
    """corrkit by validate-draft --help exits 0."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "by", "validate-draft", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "draft" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 6. 'for add' creates correct files
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "src" / "collab" / "templates"
VOICE_FILE = Path(__file__).resolve().parent.parent / "voice.md"


def test_collab_add_creates_correct_files(tmp_path):
    """'for add' file-creation logic produces all expected files."""
    name = "helper"
    owner_name = "Brian"

    # Replicate the file-creation logic from collab.add.main()
    (tmp_path / "AGENTS.md").write_text(
        _generate_agents_md(name, owner_name), encoding="utf-8"
    )
    os.symlink("AGENTS.md", tmp_path / "CLAUDE.md")
    (tmp_path / "README.md").write_text(
        _generate_readme_md(name, owner_name), encoding="utf-8"
    )
    (tmp_path / ".gitignore").write_text(
        "AGENTS.local.md\nCLAUDE.local.md\n__pycache__/\n", encoding="utf-8"
    )
    if VOICE_FILE.exists():
        shutil.copy2(VOICE_FILE, tmp_path / "voice.md")
    (tmp_path / "conversations").mkdir()
    (tmp_path / "conversations" / ".gitkeep").touch()
    (tmp_path / "drafts").mkdir()
    (tmp_path / "drafts" / ".gitkeep").touch()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    notify_src = TEMPLATES_DIR / "notify.yml"
    if notify_src.exists():
        shutil.copy2(notify_src, tmp_path / ".github" / "workflows" / "notify.yml")

    # Verify all expected files exist
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "CLAUDE.md").is_symlink()
    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / ".gitignore").is_file()
    assert (tmp_path / "voice.md").is_file()
    assert (tmp_path / "conversations" / ".gitkeep").is_file()
    assert (tmp_path / "drafts" / ".gitkeep").is_file()
    assert (tmp_path / ".github" / "workflows" / "notify.yml").is_file()

    # CLAUDE.md symlink points to AGENTS.md
    assert os.readlink(tmp_path / "CLAUDE.md") == "AGENTS.md"

    # AGENTS.md contains collaborator name in Author field
    agents_content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert f"**Author**: {name}" in agents_content

    # README.md uses owner name
    readme_content = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert f"**Author**: {name}" in readme_content
    assert f"Shared Correspondence with {owner_name}" in readme_content

    # .gitignore contains expected entries
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "AGENTS.local.md" in gitignore
    assert "CLAUDE.local.md" in gitignore
    assert "__pycache__/" in gitignore


# ---------------------------------------------------------------------------
# 7. README.md template includes all sections
# ---------------------------------------------------------------------------


def test_readme_md_template_completeness():
    """Expanded README.md template includes all required sections and content."""
    md = _generate_readme_md("drafter", owner_name="Brian")

    # Title
    assert "# Shared Correspondence with Brian" in md

    # Quick start
    assert "## Quick start" in md

    # All four workflow sections
    assert "### 1. Read conversations" in md
    assert "### 2. Find threads that need a reply" in md
    assert "### 3. Draft a reply" in md
    assert "### 4. Validate and push" in md

    # Draft template with parameterized Author
    assert "**Author**: drafter" in md
    assert "**Status**: review" in md

    # Commands reference uvx corrkit
    assert "uvx corrkit by find-unanswered" in md
    assert "uvx corrkit by validate-draft" in md

    # Reference section pointing to AGENTS.md
    assert "## Reference" in md
    assert "AGENTS.md" in md
