"""Use case for clearing inline-query sticker caches."""

from __future__ import annotations

from bot.application.errors import UserNotFoundError
from bot.application.ports import UserRepository
from bot.application.requests import ClearInlineCacheCommand
from bot.application.results import AcknowledgementResult
from bot.domain.services import StickerPackService
from bot.domain.user import StickfixUser


class ClearInlineCache:
    """Clear cached stickers for the effective inline cache owner."""

    def __init__(
        self,
        users: UserRepository,
        stickers: StickerPackService | None = None,
    ) -> None:
        self._users = users
        self._stickers = stickers or StickerPackService()

    def __call__(self, command: ClearInlineCacheCommand) -> AcknowledgementResult:
        public_pack = self._users.get_public_pack()
        user = self._resolve_request_user(command.user_id, public_pack)
        cache_owner = self._stickers.resolve_effective_pack(user, public_pack)
        cache_owner.remove_cached_stickers()
        self._users.save_user(cache_owner)
        return AcknowledgementResult(acknowledged=True)

    def _resolve_request_user(
        self,
        user_id: str | None,
        public_pack: StickfixUser | None,
    ) -> StickfixUser:
        user = self._users.get_user(user_id) if user_id is not None else None
        if user is not None:
            return user
        if public_pack is None:
            raise UserNotFoundError("No user or public sticker pack exists.")
        return public_pack
