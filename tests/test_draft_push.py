"""Tests for draft push: parsing, composition, status validation."""

import pytest

from draft.push import (
    VALID_SEND_STATUSES,
    _update_draft_status,
    compose_email,
    parse_draft,
)

BASIC_DRAFT = """\
# Test Subject

**To**: alice@example.com
**Status**: draft
**Author**: alex

---

Hello, this is the body.
"""

REVIEW_DRAFT = """\
# Re: Project Update

**To**: bob@example.com
**CC**: carol@example.com
**Status**: review
**Author**: alex
**In-Reply-To**: <msg-123@mail.example.com>

---

Thanks for the update. Here are my thoughts.
"""


def test_parse_draft_basic(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text(BASIC_DRAFT, encoding="utf-8")

    meta, subject, body = parse_draft(p)
    assert subject == "Test Subject"
    assert meta["To"] == "alice@example.com"
    assert meta["Status"] == "draft"
    assert meta["Author"] == "alex"
    assert "Hello, this is the body." in body


def test_parse_draft_with_reply_metadata(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text(REVIEW_DRAFT, encoding="utf-8")

    meta, subject, body = parse_draft(p)
    assert subject == "Re: Project Update"
    assert meta["CC"] == "carol@example.com"
    assert meta["In-Reply-To"] == "<msg-123@mail.example.com>"


def test_parse_draft_missing_to(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text("# Subject\n\n**Status**: draft\n\n---\n\nBody\n")
    with pytest.raises(SystemExit, match="missing.*To"):
        parse_draft(p)


def test_parse_draft_missing_separator(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text("# Subject\n\n**To**: a@b.com\n\nNo separator\n")
    with pytest.raises(SystemExit, match="missing.*---"):
        parse_draft(p)


def test_compose_email_basic(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text(BASIC_DRAFT, encoding="utf-8")
    meta, subject, body = parse_draft(p)

    msg = compose_email(meta, subject, body)
    assert msg["To"] == "alice@example.com"
    assert msg["Subject"] == "Test Subject"
    assert "Hello, this is the body." in msg.get_content()


def test_compose_email_with_reply_headers(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text(REVIEW_DRAFT, encoding="utf-8")
    meta, subject, body = parse_draft(p)

    msg = compose_email(meta, subject, body)
    assert msg["CC"] == "carol@example.com"
    assert msg["In-Reply-To"] == "<msg-123@mail.example.com>"
    assert msg["References"] == "<msg-123@mail.example.com>"


def test_update_draft_status(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text(REVIEW_DRAFT, encoding="utf-8")

    _update_draft_status(p, "sent")

    updated = p.read_text(encoding="utf-8")
    assert "**Status**: sent" in updated
    # Other fields unchanged
    assert "**Author**: alex" in updated
    assert "**To**: bob@example.com" in updated


def test_update_draft_status_preserves_body(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text(REVIEW_DRAFT, encoding="utf-8")

    _update_draft_status(p, "approved")

    updated = p.read_text(encoding="utf-8")
    assert "Thanks for the update." in updated
    assert "**Status**: approved" in updated


def test_valid_send_statuses():
    assert "review" in VALID_SEND_STATUSES
    assert "approved" in VALID_SEND_STATUSES
    assert "draft" not in VALID_SEND_STATUSES
    assert "sent" not in VALID_SEND_STATUSES
