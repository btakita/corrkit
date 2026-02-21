"""Tests for IMAP sync: parsing, merge, routing, helpers."""

from pathlib import Path

from sync.imap import (
    _build_label_routes,
    _cleanup_orphans,
    _merge_message_to_file,
    _parse_msg_date,
    _set_mtime,
    _unique_slug,
    parse_thread_markdown,
    slugify,
    thread_key_from_subject,
    thread_to_markdown,
)
from sync.types import Message, Thread

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert slugify("Re: Important! (urgent)") == "re-important-urgent"


def test_slugify_truncates():
    long = "a" * 100
    assert len(slugify(long)) <= 60


def test_slugify_empty():
    assert slugify("!!!") == "untitled"


def test_thread_key_strips_re():
    assert thread_key_from_subject("Re: Hello") == "hello"
    assert thread_key_from_subject("Fwd: Hello") == "hello"
    assert thread_key_from_subject("RE: FW: nested") == "fw: nested"


def test_thread_key_plain():
    assert thread_key_from_subject("New topic") == "new topic"


def test_unique_slug_no_collision(tmp_path):
    assert _unique_slug(tmp_path, "hello") == "hello"


def test_unique_slug_with_collision(tmp_path):
    (tmp_path / "hello.md").touch()
    assert _unique_slug(tmp_path, "hello") == "hello-2"


def test_unique_slug_multiple_collisions(tmp_path):
    (tmp_path / "hello.md").touch()
    (tmp_path / "hello-2.md").touch()
    assert _unique_slug(tmp_path, "hello") == "hello-3"


# ---------------------------------------------------------------------------
# Markdown round-trip
# ---------------------------------------------------------------------------

SAMPLE_THREAD = Thread(
    id="thread-123",
    subject="Project Update",
    labels=["correspondence", "for-alex"],
    accounts=["personal"],
    messages=[
        Message(
            id="1",
            thread_id="project update",
            from_="Alice <alice@example.com>",
            date="Mon, 10 Feb 2025 10:00:00 +0000",
            subject="Project Update",
            body="Here is the update.",
        ),
        Message(
            id="2",
            thread_id="project update",
            from_="Bob <bob@example.com>",
            date="Mon, 10 Feb 2025 11:00:00 +0000",
            subject="Re: Project Update",
            body="Thanks for the update.",
        ),
    ],
    last_date="Mon, 10 Feb 2025 11:00:00 +0000",
)


def test_thread_to_markdown_structure():
    md = thread_to_markdown(SAMPLE_THREAD)
    assert md.startswith("# Project Update")
    assert "**Labels**: correspondence, for-alex" in md
    assert "**Accounts**: personal" in md
    assert "**Thread ID**: thread-123" in md
    assert "## Alice <alice@example.com>" in md
    assert "## Bob <bob@example.com>" in md
    assert "Here is the update." in md
    assert "Thanks for the update." in md


def test_parse_thread_markdown_round_trip():
    md = thread_to_markdown(SAMPLE_THREAD)
    parsed = parse_thread_markdown(md)

    assert parsed is not None
    assert parsed.subject == "Project Update"
    assert parsed.id == "thread-123"
    assert parsed.labels == ["correspondence", "for-alex"]
    assert parsed.accounts == ["personal"]
    assert len(parsed.messages) == 2
    assert parsed.messages[0].from_ == "Alice <alice@example.com>"
    assert "Here is the update." in parsed.messages[0].body


def test_parse_thread_markdown_legacy_label():
    """Backward compat: single **Label** field parsed into labels list."""
    md = (
        "# Test\n\n"
        "**Label**: correspondence\n"
        "**Thread ID**: t1\n"
        "**Last updated**: Mon, 10 Feb 2025\n"
    )
    parsed = parse_thread_markdown(md)
    assert parsed is not None
    assert parsed.labels == ["correspondence"]


def test_parse_thread_markdown_empty():
    assert parse_thread_markdown("") is None
    assert parse_thread_markdown("no heading here") is None


# ---------------------------------------------------------------------------
# mtime
# ---------------------------------------------------------------------------


def test_set_mtime(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("hello")
    _set_mtime(f, "Mon, 10 Feb 2025 14:30:00 +0000")
    expected = _parse_msg_date("Mon, 10 Feb 2025 14:30:00 +0000").timestamp()
    assert abs(f.stat().st_mtime - expected) < 1


def test_set_mtime_invalid_date_no_op(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("hello")
    original_mtime = f.stat().st_mtime
    _set_mtime(f, "not a date")
    assert f.stat().st_mtime == original_mtime


# ---------------------------------------------------------------------------
# Merge to file
# ---------------------------------------------------------------------------


def test_merge_creates_new_file(tmp_path):
    out_dir = tmp_path / "conversations"
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )

    _merge_message_to_file(out_dir, "test-label", "personal", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    assert files[0].name == "hello.md"  # immutable slug, no date
    content = files[0].read_text(encoding="utf-8")
    assert "# Hello" in content
    assert "Alice <alice@example.com>" in content
    assert "**Labels**: test-label" in content
    assert "**Accounts**: personal" in content


def test_merge_deduplicates(tmp_path):
    out_dir = tmp_path / "conversations"
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )

    _merge_message_to_file(out_dir, "test-label", "personal", msg, "hello")
    _merge_message_to_file(out_dir, "test-label", "personal", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    # Should only have one message section
    assert content.count("## Alice") == 1


def test_merge_appends_new_message(tmp_path):
    out_dir = tmp_path / "conversations"
    msg1 = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )
    msg2 = Message(
        id="2",
        thread_id="hello",
        from_="Bob <bob@example.com>",
        date="Mon, 10 Feb 2025 11:00:00 +0000",
        subject="Re: Hello",
        body="Hey Alice!",
    )

    _merge_message_to_file(out_dir, "test-label", "personal", msg1, "hello")
    _merge_message_to_file(out_dir, "test-label", "personal", msg2, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    assert files[0].name == "hello.md"  # filename didn't change
    content = files[0].read_text(encoding="utf-8")
    assert "Alice" in content
    assert "Bob" in content


def test_merge_accumulates_labels(tmp_path):
    """Same thread synced from different labels accumulates labels."""
    out_dir = tmp_path / "conversations"
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )

    _merge_message_to_file(out_dir, "correspondence", "personal", msg, "hello")
    _merge_message_to_file(out_dir, "for-alex", "personal", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "**Labels**: correspondence, for-alex" in content


def test_merge_accumulates_accounts(tmp_path):
    """Same thread from different accounts accumulates accounts."""
    out_dir = tmp_path / "conversations"
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )

    _merge_message_to_file(out_dir, "inbox", "personal", msg, "hello")
    _merge_message_to_file(out_dir, "inbox", "proton", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "**Accounts**: personal, proton" in content


def test_merge_sets_mtime(tmp_path):
    out_dir = tmp_path / "conversations"
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )

    _merge_message_to_file(out_dir, "test-label", "personal", msg, "hello")

    files = list(out_dir.glob("*.md"))
    expected = _parse_msg_date("Mon, 10 Feb 2025 10:00:00 +0000").timestamp()
    assert abs(files[0].stat().st_mtime - expected) < 1


def test_merge_slug_collision(tmp_path):
    """Different threads with same subject get unique filenames."""
    out_dir = tmp_path / "conversations"
    msg1 = Message(
        id="1",
        thread_id="thread-a",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="First thread.",
    )
    msg2 = Message(
        id="2",
        thread_id="thread-b",
        from_="Bob <bob@example.com>",
        date="Tue, 11 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Different thread, same subject.",
    )

    _merge_message_to_file(out_dir, "label", "personal", msg1, "thread-a")
    _merge_message_to_file(out_dir, "label", "personal", msg2, "thread-b")

    files = sorted(f.name for f in out_dir.glob("*.md"))
    assert len(files) == 2
    assert "hello.md" in files
    assert "hello-2.md" in files


# ---------------------------------------------------------------------------
# Orphan cleanup
# ---------------------------------------------------------------------------


def test_cleanup_orphans(tmp_path):
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    kept = conv_dir / "kept.md"
    kept.write_text("keep me")
    orphan = conv_dir / "orphan.md"
    orphan.write_text("remove me")

    _cleanup_orphans(conv_dir, {kept})

    assert kept.exists()
    assert not orphan.exists()


def test_cleanup_orphans_empty_dir(tmp_path):
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    _cleanup_orphans(conv_dir, set())  # no error


def test_cleanup_orphans_missing_dir(tmp_path):
    _cleanup_orphans(tmp_path / "nope", set())  # no error


# ---------------------------------------------------------------------------
# Label routing
# ---------------------------------------------------------------------------


def test_build_label_routes_with_collaborators(tmp_path, monkeypatch):
    from collab import Collaborator, save_collaborators

    config = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex-gh": Collaborator(
                labels=["for-alex"], github_user="alex-gh", repo="o/to-alex-gh"
            ),
            "bot-agent": Collaborator(
                labels=["for-bot", "triage"],
                github_user="bot-agent",
                repo="o/to-bot-agent",
            ),
        },
        config,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config)

    routes = _build_label_routes()

    assert routes["for-alex"] == Path("correspondence/for/alex-gh/conversations")
    assert routes["for-bot"] == Path("correspondence/for/bot-agent/conversations")
    assert routes["triage"] == Path("correspondence/for/bot-agent/conversations")


def test_build_label_routes_account_scoped_labels(tmp_path, monkeypatch):
    """account:label syntax scopes a label to a specific account."""
    from collab import Collaborator, save_collaborators

    config = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "bot-agent": Collaborator(
                labels=["for-bot", "proton-dev:INBOX"],
                github_user="bot-agent",
                repo="o/to-bot-agent",
            ),
        },
        config,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config)

    # When syncing personal: only for-bot (plain label), not INBOX
    routes_personal = _build_label_routes("personal")
    assert "for-bot" in routes_personal
    assert "INBOX" not in routes_personal

    # When syncing proton-dev: both for-bot and INBOX
    routes_proton = _build_label_routes("proton-dev")
    assert "for-bot" in routes_proton
    assert "INBOX" in routes_proton
    assert routes_proton["INBOX"] == Path("correspondence/for/bot-agent/conversations")

    # No account filter: both included
    routes_all = _build_label_routes()
    assert "for-bot" in routes_all
    assert "INBOX" in routes_all


def test_build_label_routes_account_scoped_with_collab_account(tmp_path, monkeypatch):
    """account:label combined with collaborator-level account field."""
    from collab import Collaborator, save_collaborators

    config = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "bot-agent": Collaborator(
                labels=["for-bot", "proton-dev:INBOX"],
                github_user="bot-agent",
                repo="o/to-bot-agent",
                account="personal",
            ),
        },
        config,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config)

    # personal: for-bot (bound by collab.account) + not INBOX
    routes = _build_label_routes("personal")
    assert "for-bot" in routes
    assert "INBOX" not in routes

    # proton-dev: INBOX (by account:label) + NOT for-bot
    routes = _build_label_routes("proton-dev")
    assert "INBOX" in routes
    assert "for-bot" not in routes


def test_build_label_routes_empty(tmp_path, monkeypatch):
    config = tmp_path / "nonexistent.toml"
    monkeypatch.setattr("collab.CONFIG_PATH", config)

    routes = _build_label_routes()
    assert routes == {}
