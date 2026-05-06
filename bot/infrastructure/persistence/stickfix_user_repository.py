"""UserRepository adapter backed by legacy StickfixDB storage.

This adapter implements the UserRepository port by delegating to StickfixDB,
which provides YAML-file-based persistence. It serves as the bridge between
the application layer (which depends on UserRepository) and the legacy storage
engine (which uses YAML files and in-memory caching).

The adapter is intentionally thin: each port method maps directly to a StickfixDB
operation with minimal logic. This enables:
- Use cases to remain agnostic of YAML/file details
- Tests to inject in-memory fakes without filesystem overhead
- Future storage backends to be swapped by implementing the port

Architecture:
    Use Cases ─(depend on)─> UserRepository (port)
                                  ↓
                         StickfixUserRepository (this adapter)
                                  ↓
                         StickfixDB (YAML storage)
"""

from __future__ import annotations

from bot.application.ports import UserRepository
from bot.database.storage import StickfixDB
from bot.domain.user import SF_PUBLIC, StickfixUser


class StickfixUserRepository(UserRepository):
    """Implement UserRepository by delegating to StickfixDB.

    This adapter is a thin wrapper that translates port method calls into
    StickfixDB operations. It does not implement caching, validation, or
    business logic—those are the responsibility of use cases and domain
    objects.

    All mutations (add, update, delete) are delegated immediately to the
    underlying StickfixDB store, which handles YAML persistence.

    Attributes:
        _store: The StickfixDB instance providing YAML-file persistence.
    """

    def __init__(self, store: StickfixDB) -> None:
        """Initialize with a StickfixDB storage backend.

        Args:
            store: The StickfixDB instance to delegate persistence to.
                  StickfixDB manages YAML files and in-memory caching.
        """
        self._store = store

    def get_user(self, user_id: str) -> StickfixUser | None:
        """Retrieve a user from StickfixDB.

        Args:
            user_id: The Telegram user ID or special pack ID (e.g., 'SF_PUBLIC').

        Returns:
            The user if it exists in StickfixDB, otherwise None.
        """
        return self._store.get(user_id)

    def has_user(self, user_id: str) -> bool:
        """Check whether a user exists in StickfixDB.

        Args:
            user_id: The Telegram user ID or special pack ID.

        Returns:
            True if the user exists, False otherwise.
        """
        return user_id in self._store

    def save_user(self, user: StickfixUser) -> None:
        """Persist a user mutation to StickfixDB.

        The user is saved immediately with all accumulated mutations
        (sticker packs, mode, cache state). StickfixDB handles YAML
        serialization and file I/O.

        Args:
            user: The user with all desired mutations applied.
        """
        self._store[user.id] = user

    def delete_user(self, user_id: str) -> bool:
        """Remove a user from StickfixDB.

        Args:
            user_id: The Telegram user ID to delete.

        Returns:
            True if a user was deleted, False if the user did not exist.
        """
        if user_id not in self._store:
            return False
        del self._store[user_id]
        return True

    def get_public_pack(self) -> StickfixUser | None:
        """Retrieve the public pack from StickfixDB.

        The public pack is stored as a special user with ID 'SF_PUBLIC'.
        This method is a convenience for callers who want to access the
        public pack without hardcoding the special ID.

        Returns:
            The public pack if it exists, otherwise None.
        """
        return self.get_user(SF_PUBLIC)

    def ensure_public_pack(self) -> StickfixUser:
        """Return the public pack, creating it if necessary.

        If the public pack does not exist in StickfixDB, it is created,
        saved, and returned. This method is safe to call unconditionally;
        callers do not need to handle the absent case.

        Returns:
            The public pack, either from StickfixDB or freshly created.
        """
        public_pack = self.get_public_pack()
        if public_pack is None:
            public_pack = StickfixUser(SF_PUBLIC)
            self.save_user(public_pack)
        return public_pack
