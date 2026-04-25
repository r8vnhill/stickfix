"""UserRepository adapter for the legacy StickfixDB store."""

from __future__ import annotations

from bot.application.ports import UserRepository
from bot.database.storage import StickfixDB
from bot.domain.user import SF_PUBLIC, StickfixUser


class StickfixUserRepository(UserRepository):
    """Expose `StickfixDB` through the application-facing user port."""

    def __init__(self, store: StickfixDB) -> None:
        self._store = store

    def get_user(self, user_id: str) -> StickfixUser | None:
        return self._store.get(user_id)

    def has_user(self, user_id: str) -> bool:
        return user_id in self._store

    def save_user(self, user: StickfixUser) -> None:
        self._store[user.id] = user

    def delete_user(self, user_id: str) -> bool:
        if user_id not in self._store:
            return False
        del self._store[user_id]
        return True

    def get_public_pack(self) -> StickfixUser | None:
        return self.get_user(SF_PUBLIC)

    def ensure_public_pack(self) -> StickfixUser:
        public_pack = self.get_public_pack()
        if public_pack is None:
            public_pack = StickfixUser(SF_PUBLIC)
            self.save_user(public_pack)
        return public_pack
