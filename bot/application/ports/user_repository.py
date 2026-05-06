"""Repository port for user and public-pack persistence.

This port abstracts storage of Stickfix users and the shared public pack, enabling:
- Use cases to persist user state (sticker packs, mode, cache) without importing
  Telegram or knowing about YAML/database internals
- Tests to provide in-memory fakes with full user mutability
- Alternative storage backends (e.g., database) by implementing this protocol

In Stickfix, the public pack is stored as a special user (ID: `SF_PUBLIC`). This port
exposes both regular users and the public pack through a single interface.

Adapters (e.g., StickfixUserRepository) implement this port by delegating to
concrete storage engines (e.g., StickfixDB YAML files).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bot.domain.user import StickfixUser


@runtime_checkable
class UserRepository(Protocol):
    """Contract for reading and mutating Stickfix users and the public pack."""

    def get_user(self, user_id: str) -> StickfixUser | None:
        """Return one user by id, or `None` when absent.

        Args:
            user_id: The Telegram user ID (as string) or special pack ID (e.g., 'SF_PUBLIC').

        Returns:
            The user/pack if found, otherwise None.
        """

    def has_user(self, user_id: str) -> bool:
        """Return whether a user exists.

        Args:
            user_id: The Telegram user ID or special pack ID.

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

    def delete_user(self, user_id: str) -> bool:
        """Delete one user, returning whether a user was removed.

        Args:
            user_id: The Telegram user ID to delete.

        Returns:
            True if a user was deleted, False if the user did not exist.
        """

    def get_public_pack(self) -> StickfixUser | None:
        """Return the shared public pack when present.

        The public pack (ID: 'SF_PUBLIC') is a special user accessible to all
        Stickfix users. Use this to retrieve the public pack without knowing
        its special ID.

        Returns:
            The public pack if it exists, otherwise None.
        """

    def ensure_public_pack(self) -> StickfixUser:
        """Return the shared public pack, creating it when necessary.

        If the public pack does not exist, it is created and returned.
        Callers should not need to handle its absence.

        Returns:
            The public pack (created if it did not exist).
        """
