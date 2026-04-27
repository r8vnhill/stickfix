"""Use case for retrieving stickers by tag."""

from __future__ import annotations

from bot.application.errors import UserNotFoundError, WrongInteractionContextError
from bot.application.ports import UserRepository
from bot.application.requests import GetStickersQuery
from bot.application.results import GetStickersResult
from bot.domain.services import StickerPackService
from bot.domain.user import UserModes


class GetStickers:
    """Resolve sticker ids for a private-chat `/get` command."""

    def __init__(self, users: UserRepository, stickers: StickerPackService | None = None) -> None:
        self._users = users
        self._stickers = stickers or StickerPackService()

    def __call__(self, query: GetStickersQuery) -> GetStickersResult:
        if query.chat_type != UserModes.PRIVATE:
            raise WrongInteractionContextError("The /get command only works in private chats.")

        public_pack = self._users.get_public_pack()
        user = self._users.get_user(query.user_id) or public_pack
        if user is None:
            raise UserNotFoundError("No user or public sticker pack exists.")

        sticker_ids = self._stickers.find_stickers(user, query.tags, public_pack)
        return GetStickersResult(sticker_ids=sticker_ids)
