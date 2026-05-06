"""Filesystem-backed help-content adapter.

This adapter implements the HelpContentProvider port by reading help text from a
UTF-8 file. It's the concrete implementation used by the application layer when
loading help content during inline query resolution.

The adapter is intentionally thin:
- Reads the file on every call (no caching in this cycle)
- Preserves file content exactly (no Markdown parsing)
- Delegates filesystem concerns to pathlib.Path

Telegram parse modes and article formatting remain the handler's responsibility.
"""

from __future__ import annotations

from pathlib import Path

from bot.application.ports import HelpContentProvider


class FileHelpContentProvider(HelpContentProvider):
    """Load help text from a UTF-8 file on every call.

    This adapter reads the help file each time get_help_text() is called,
    so changes to the file are reflected immediately. Caching is not included
    in this implementation and may be added in a future cycle if needed.

    Attributes:
        _path: The filesystem path to read help text from.
    """

    def __init__(self, path: Path) -> None:
        """Initialize with the path to the help file.

        Args:
            path: The filesystem path to read help text from. Can be absolute or
                  relative. Must be readable with UTF-8 encoding.

        Raises:
            FileNotFoundError: If the path does not exist (raised on first read,
                             not during initialization).
        """
        self._path = path

    def get_help_text(self) -> str:
        """Read and return the current help file content.

        Reads the file with UTF-8 encoding and returns the content unchanged.
        No Markdown parsing, caching, or filtering is applied.

        Returns:
            The raw file content as a string.

        Raises:
            FileNotFoundError: If the configured file does not exist.
            UnicodeDecodeError: If the file is not valid UTF-8.
        """
        return self._path.read_text(encoding="utf-8")
