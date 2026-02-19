"""Tests for gmail sync: parsing, merge, routing, helpers."""

from pathlib import Path

from sync.gmail import (
    _build_label_routes,
    _merge_message_to_file,
    date_prefix_from,
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


def test_date_prefix_valid():
    assert date_prefix_from("Mon, 10 Feb 2025 14:30:00 +0000") == "2025-02-10"


def test_date_prefix_invalid_falls_back():
    prefix = date_prefix_from("not a date")
    # Should return today's date (YYYY-MM-DD format)
    assert len(prefix) == 10
    assert prefix[4] == "-"


# ---------------------------------------------------------------------------
# Markdown round-trip
# ---------------------------------------------------------------------------

SAMPLE_THREAD = Thread(
    id="thread-123",
    label="correspondence",
    subject="Project Update",
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
    assert "**Label**: correspondence" in md
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
    assert parsed.label == "correspondence"
    assert len(parsed.messages) == 2
    assert parsed.messages[0].from_ == "Alice <alice@example.com>"
    assert "Here is the update." in parsed.messages[0].body


def test_parse_thread_markdown_empty():
    assert parse_thread_markdown("") is None
    assert parse_thread_markdown("no heading here") is None


# ---------------------------------------------------------------------------
# Merge to file
# ---------------------------------------------------------------------------


def test_merge_creates_new_file(tmp_path):
    out_dir = tmp_path / "conversations" / "test-label"
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )

    _merge_message_to_file(out_dir, "test-label", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "# Hello" in content
    assert "Alice <alice@example.com>" in content
    assert "2025-02-10" in files[0].name


def test_merge_deduplicates(tmp_path):
    out_dir = tmp_path / "conversations" / "test-label"
    msg = Message(
        id="1",
        thread_id="hello",
        from_="Alice <alice@example.com>",
        date="Mon, 10 Feb 2025 10:00:00 +0000",
        subject="Hello",
        body="Hi there.",
    )

    _merge_message_to_file(out_dir, "test-label", msg, "hello")
    _merge_message_to_file(out_dir, "test-label", msg, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    # Should only have one message section
    assert content.count("## Alice") == 1


def test_merge_appends_new_message(tmp_path):
    out_dir = tmp_path / "conversations" / "test-label"
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

    _merge_message_to_file(out_dir, "test-label", msg1, "hello")
    _merge_message_to_file(out_dir, "test-label", msg2, "hello")

    files = list(out_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Alice" in content
    assert "Bob" in content


# ---------------------------------------------------------------------------
# Label routing
# ---------------------------------------------------------------------------


def test_build_label_routes_with_collaborators(tmp_path, monkeypatch):
    from collab import Collaborator, save_collaborators

    config = tmp_path / "collaborators.toml"
    save_collaborators(
        {
            "alex": Collaborator(labels=["for-alex"], repo="o/shared-alex"),
            "bot": Collaborator(labels=["for-bot", "triage"], repo="o/shared-bot"),
        },
        config,
    )
    monkeypatch.setattr("collab.CONFIG_PATH", config)

    routes = _build_label_routes()

    assert routes["for-alex"] == Path("shared/alex/conversations/for-alex")
    assert routes["for-bot"] == Path("shared/bot/conversations/for-bot")
    assert routes["triage"] == Path("shared/bot/conversations/triage")


def test_build_label_routes_empty(tmp_path, monkeypatch):
    config = tmp_path / "nonexistent.toml"
    monkeypatch.setattr("collab.CONFIG_PATH", config)

    routes = _build_label_routes()
    assert routes == {}
