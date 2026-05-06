"""Tests for FileHelpContentProvider."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.infrastructure.help import FileHelpContentProvider


class TestFileHelpContentProvider:
    """Contract tests for FileHelpContentProvider."""

    def test_reads_help_text_from_utf8_file(self, tmp_path: Path) -> None:
        """Adapter reads UTF-8 file content unchanged."""
        help_file = tmp_path / "HELP.md"
        help_file.write_text("# Help\n\nUse /add ✨\n", encoding="utf-8")

        provider = FileHelpContentProvider(help_file)

        assert provider.get_help_text() == "# Help\n\nUse /add ✨\n"

    def test_reads_current_file_content_on_each_call(self, tmp_path: Path) -> None:
        """Adapter does not cache stale content; reads file on each call."""
        help_file = tmp_path / "HELP.md"
        help_file.write_text("first", encoding="utf-8")

        provider = FileHelpContentProvider(help_file)

        assert provider.get_help_text() == "first"

        # Modify file after provider is created
        help_file.write_text("second", encoding="utf-8")

        # Next call should reflect current file content
        assert provider.get_help_text() == "second"

    def test_raises_when_help_file_is_missing(self, tmp_path: Path) -> None:
        """Adapter raises FileNotFoundError when file does not exist."""
        provider = FileHelpContentProvider(tmp_path / "missing.md")

        with pytest.raises(FileNotFoundError):
            provider.get_help_text()

    def test_handles_empty_help_file(self, tmp_path: Path) -> None:
        """Adapter returns empty string for empty file."""
        help_file = tmp_path / "HELP.md"
        help_file.write_text("", encoding="utf-8")

        provider = FileHelpContentProvider(help_file)

        assert provider.get_help_text() == ""

    def test_preserves_whitespace_and_special_characters(self, tmp_path: Path) -> None:
        """Adapter preserves exact file content including whitespace."""
        help_file = tmp_path / "HELP.md"
        content = "Line 1\n\nLine 3 with   spaces\n\tTab indent\n"
        help_file.write_text(content, encoding="utf-8")

        provider = FileHelpContentProvider(help_file)

        assert provider.get_help_text() == content
