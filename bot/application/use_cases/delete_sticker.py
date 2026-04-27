"""Use case for removing a sticker from the effective sticker pack."""

from __future__ import annotations

from bot.application.errors import MissingStickerError, UserNotFoundError
from bot.application.ports import UserRepository
from bot.application.requests import DeleteStickerCommand
from bot.application.results import DeleteStickerResult
from bot.domain.services import StickerPackService


class DeleteSticker:
    """Remove a sticker from the public or private pack selected by user settings."""

    def __init__(self, users: UserRepository, stickers: StickerPackService | None = None) -> None:
        self._users = users
        self._stickers = stickers or StickerPackService()

    def __call__(self, command: DeleteStickerCommand) -> DeleteStickerResult:
        if command.reply_sticker_id is None:
            raise MissingStickerError("A sticker id is required to delete a sticker.")

        public_pack = self._users.get_public_pack()
        user = self._users.get_user(command.user_id) or public_pack
        if user is None:
            raise UserNotFoundError("No user or public sticker pack exists.")

        mutation = self._stickers.delete_sticker(
            user,
            command.reply_sticker_id,
            command.tags,
            public_pack,
        )
        self._users.save_user(mutation.effective_pack)
        return DeleteStickerResult(
            sticker_id=command.reply_sticker_id,
            effective_tags=command.tags,
            changed=mutation.changed,
        )
