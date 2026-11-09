"""Persistence contract for the shared public sticker pack."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from expression import Option
from stickfix_domain import StickfixUser


@runtime_checkable
class PublicPackRepository(Protocol):
  """Load and persist the shared pack without exposing a synthetic user id."""

  def get(self) -> Option[StickfixUser]:
    """Return a detached public pack in `Some` when associations are persisted.

    Empty public sticker and cache associations are represented as absence and
    therefore return `Nothing`.
    """

  def save(self, pack: StickfixUser) -> None:
    """Persist a snapshot of the pack's sticker/cache associations."""

  def ensure(self) -> StickfixUser:
    """Return a pack object, creating an unsaved canonical empty pack if absent."""
