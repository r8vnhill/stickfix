"""Repository port for user and public-pack access."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bot.domain.user import StickfixUser


@runtime_checkable
class UserRepository(Protocol):
    """Application-facing contract for accessing Stickfix users."""

    def get_user(self, user_id: str) -> StickfixUser | None:
        """Return one user by id, or `None` when absent."""

    def has_user(self, user_id: str) -> bool:
        """Return whether a user exists."""

    def save_user(self, user: StickfixUser) -> None:
        """Persist one user in the repository."""

    def delete_user(self, user_id: str) -> bool:
        """Delete one user, returning whether a user was removed."""

    def get_public_pack(self) -> StickfixUser | None:
        """Return the shared public pack when present."""

    def ensure_public_pack(self) -> StickfixUser:
        """Return the shared public pack, creating it when necessary."""
