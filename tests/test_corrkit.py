"""Tests for the corrkit unified CLI dispatcher."""

import subprocess


def test_help_flag_shows_all_commands():
    """corrkit --help lists every subcommand."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for cmd in [
        "sync",
        "sync-gmail",
        "list-folders",
        "push-draft",
        "for add",
        "for sync",
        "for status",
        "for remove",
        "by find-unanswered",
        "by validate-draft",
        "audit-docs",
        "help",
    ]:
        assert cmd in result.stdout


def test_no_args_shows_help():
    """corrkit with no arguments shows the help table."""
    result = subprocess.run(
        ["uv", "run", "corrkit"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "sync-gmail" in result.stdout


def test_subcommand_help():
    """corrkit sync-gmail --help shows sync-gmail flags."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "sync-gmail", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--full" in result.stdout


def test_list_folders_help():
    """corrkit list-folders --help shows usage."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "list-folders", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "account" in result.stdout.lower()


def test_unknown_subcommand_exits_nonzero():
    """Unknown subcommand exits with non-zero status."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "no-such-command"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Unknown command" in result.stderr


def test_nested_for_add_help():
    """corrkit for add --help exits 0."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "for", "add", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "collaborator" in result.stdout.lower()


def test_nested_by_find_unanswered_help():
    """corrkit by find-unanswered --help exits 0."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "by", "find-unanswered", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "reply" in result.stdout.lower()


def test_unknown_nested_command_exits_nonzero():
    """Unknown nested command exits with non-zero status."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "for", "no-such-sub"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Unknown command: for no-such-sub" in result.stderr


def test_nested_group_without_subcommand_shows_help():
    """corrkit for (without subcommand) shows help."""
    result = subprocess.run(
        ["uv", "run", "corrkit", "for"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "for add" in result.stdout
