"""Use case for adding a sticker to the effective sticker pack."""

from __future__ import annotations

from bot.application.errors import MissingStickerError
from bot.application.ports import UserRepository
from bot.application.requests import AddStickerCommand
from bot.application.results import AddStickerResult
from bot.domain.services import StickerPackService


class AddSticker:
    """Add a sticker to the public or private pack selected by user settings."""

    def __init__(self, users: UserRepository, stickers: StickerPackService | None = None) -> None:
        self._users = users
        self._stickers = stickers or StickerPackService()

    def __call__(self, command: AddStickerCommand) -> AddStickerResult:
        if command.reply_sticker_id is None:
            raise MissingStickerError("A sticker id is required to add a sticker.")

        public_pack = self._users.ensure_public_pack()
        user = self._users.get_user(command.user_id) or public_pack
        tags = self._effective_tags(command)
        mutation = self._stickers.add_sticker(user, command.reply_sticker_id, tags, public_pack)
        if tags:
            self._users.save_user(mutation.effective_pack)
        return AddStickerResult(
            sticker_id=command.reply_sticker_id,
            effective_tags=tags,
            changed=mutation.changed,
        )

    @staticmethod
    def _effective_tags(command: AddStickerCommand) -> tuple[str, ...]:
        if command.tags:
            return command.tags
        if command.reply_sticker_emoji:
            return (command.reply_sticker_emoji,)
        return ()
