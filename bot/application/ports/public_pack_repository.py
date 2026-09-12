"""Persistence contract for the shared public sticker pack."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from stickfix_domain import StickfixUser


@runtime_checkable
class PublicPackRepository(Protocol):
  """Load and persist the shared pack without exposing a synthetic user id."""

  def get(self) -> StickfixUser | None:
    """Return the public pack when it has persisted state."""

  def save(self, pack: StickfixUser) -> None:
    """Persist the public pack and its sticker/cache associations."""

  def ensure(self) -> StickfixUser:
    """Return a pack object, creating an empty one when necessary."""
