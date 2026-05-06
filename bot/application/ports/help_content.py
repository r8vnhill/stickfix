"""Port for help-content access.

This port abstracts help-text retrieval from the application layer, enabling:
- `ResolveInlineQuery` use case to include help text without reading files directly
- Tests to provide mock help content without filesystem dependencies
- Future alternative implementations (e.g., database-backed help, multilingual variants)

Adapters (e.g., FileHelpContentProvider) implement this port by reading from
concrete storage engines.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HelpContentProvider(Protocol):
    """Contract for retrieving help text.

    Implementers must return the exact help-text content (usually plain Markdown
    read from a file). Parsing, rendering, and Telegram-specific formatting remain
    the responsibility of the handler.
    """

    def get_help_text(self) -> str:
        """Return the raw help text shown by Stickfix.

        The returned string may contain Markdown syntax but must not include
        Telegram parse modes, HTML tags, or handler-specific formatting.

        Returns:
            Plain help text, typically read from a file.

        Raises:
            FileNotFoundError: If the concrete implementation cannot access help content.
        """
