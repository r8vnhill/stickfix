"""Use case for removing a sticker from the effective sticker pack."""

from __future__ import annotations

from bot.application.errors import MissingStickerError
from bot.application.ports import PublicPackRepository, UserRepository
from bot.application.requests import DeleteStickerCommand
from bot.application.results import DeleteStickerResult
from bot.domain.services import StickerPackService

from ._repositories import public_repository, resolve_effective_user, save_effective_pack


class DeleteSticker:
    """Remove a sticker from the public or private pack selected by user settings."""

    def __init__(
        self,
        users: UserRepository,
        public: PublicPackRepository | None = None,
        stickers: StickerPackService | None = None,
    ) -> None:
        self._users = users
        self._public = public_repository(users, public)
        self._stickers = stickers or StickerPackService()

    def __call__(self, command: DeleteStickerCommand) -> DeleteStickerResult:
        if command.reply_sticker_id is None:
            raise MissingStickerError("A sticker id is required to delete a sticker.")

        public_pack = self._public.get()
        user = resolve_effective_user(self._users, command.user_id, public_pack)

        mutation = self._stickers.delete_sticker(
            user,
            command.reply_sticker_id,
            command.tags,
            public_pack,
        )
        save_effective_pack(self._users, self._public, mutation.effective_pack, public_pack)
        return DeleteStickerResult(
            sticker_id=command.reply_sticker_id,
            effective_tags=command.tags,
            changed=mutation.changed,
        )
