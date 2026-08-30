"""Use case for clearing inline-query sticker caches."""

from __future__ import annotations

from bot.application.ports import PublicPackRepository, UserRepository
from bot.application.requests import ClearInlineCacheCommand
from bot.application.results import AcknowledgementResult
from bot.domain.services import StickerPackService

from ._repositories import public_repository, resolve_effective_user, save_effective_pack


class ClearInlineCache:
    """Clear cached stickers for the effective inline cache owner."""

    def __init__(
        self,
        users: UserRepository,
        public: PublicPackRepository | None = None,
        stickers: StickerPackService | None = None,
    ) -> None:
        self._users = users
        self._public = public_repository(users, public)
        self._stickers = stickers or StickerPackService()

    def __call__(self, command: ClearInlineCacheCommand) -> AcknowledgementResult:
        public_pack = self._public.get()
        user = resolve_effective_user(self._users, command.user_id, public_pack)
        cache_owner = self._stickers.resolve_effective_pack(user, public_pack)
        cache_owner.remove_cached_stickers()
        save_effective_pack(self._users, self._public, cache_owner, public_pack)
        return AcknowledgementResult(acknowledged=True)
