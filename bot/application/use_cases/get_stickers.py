"""Use case for retrieving stickers by tag."""

from __future__ import annotations

from bot.application.errors import WrongInteractionContextError
from bot.application.ports import PublicPackRepository, UserRepository
from bot.application.requests import GetStickersQuery
from bot.application.results import GetStickersResult
from bot.domain.services import StickerPackService
from bot.domain.user import UserModes

from ._repositories import public_repository, resolve_effective_user


class GetStickers:
    """Resolve sticker ids for a private-chat `/get` command."""

    def __init__(
        self,
        users: UserRepository,
        public: PublicPackRepository | None = None,
        stickers: StickerPackService | None = None,
    ) -> None:
        self._users = users
        self._public = public_repository(users, public)
        self._stickers = stickers or StickerPackService()

    def __call__(self, query: GetStickersQuery) -> GetStickersResult:
        if query.chat_type != UserModes.PRIVATE:
            raise WrongInteractionContextError("The /get command only works in private chats.")

        public_pack = self._public.get()
        user = resolve_effective_user(self._users, query.user_id, public_pack)

        sticker_ids = self._stickers.find_stickers(user, query.tags, public_pack)
        return GetStickersResult(sticker_ids=sticker_ids)
