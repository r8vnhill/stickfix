"""Repository port for regular Telegram user persistence.

This port abstracts storage of Stickfix users and the shared public pack, enabling:
- Use cases to persist user state (sticker packs, mode, cache) without importing
  Telegram or knowing about YAML/database internals
- Tests to provide in-memory fakes with full user mutability
- Alternative storage backends (e.g., database) by implementing this protocol

The shared public pack has its own `PublicPackRepository` contract and is not represented
as a synthetic user id here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bot.domain.identifiers import UserId
from bot.domain.user import StickfixUser


@runtime_checkable
class UserRepository(Protocol):
    """Contract for reading and mutating regular Stickfix users."""

    def get_user(self, user_id: UserId) -> StickfixUser | None:
        """Return one user by id, or `None` when absent.

        Args:
            user_id: Numeric Telegram user ID.

        Returns:
            The user/pack if found, otherwise None.
        """

    def has_user(self, user_id: UserId) -> bool:
        """Return whether a user exists.

        Args:
            user_id: Numeric Telegram user ID.

        Returns:
            True if the user/pack is stored, False otherwise.
        """

    def save_user(self, user: StickfixUser) -> None:
        """Persist one user in the repository.

        Updates an existing user or inserts a new one. All mutations (sticker packs,
        mode, cache state) are saved immediately.

        Args:
            user: The user to save. Must have a valid user_id.
        """

    def delete_user(self, user_id: UserId) -> bool:
        """Delete one user, returning whether a user was removed.

        Args:
            user_id: Numeric Telegram user ID to delete.

        Returns:
            True if a user was deleted, False if the user did not exist.
        """
