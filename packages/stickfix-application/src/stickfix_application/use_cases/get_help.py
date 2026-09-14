"""Use case for retrieving the bot's help content."""

from __future__ import annotations

from ..ports import HelpContentProvider


class GetHelp:
  """Expose help content to interface adapters without file-system coupling."""

  def __init__(self, help_content: HelpContentProvider) -> None:
    self._help_content = help_content

  def __call__(self) -> str:
    return self._help_content.get_help_text()
