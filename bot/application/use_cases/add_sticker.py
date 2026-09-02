"""Use case for adding a sticker to the effective sticker pack."""

from __future__ import annotations

from bot.application.errors import MissingStickerError
from bot.application.requests import AddStickerCommand
from bot.application.results import AddStickerResult

from ._base import StickerPackUseCase
from ._repositories import save_effective_pack


class AddSticker(StickerPackUseCase):
    """Add a sticker to the public or private pack selected by user settings.

    Tag resolution mirrors the legacy bot: an explicit ``tags`` argument wins,
    otherwise the sticker's own emoji becomes the single tag, otherwise the
    sticker is added untagged. The effective pack is persisted only when there is
    at least one tag to link, matching :class:`StickerPackService` semantics.
    """

    def __call__(self, command: AddStickerCommand) -> AddStickerResult:
        if command.reply_sticker_id is None:
            raise MissingStickerError("A sticker id is required to add a sticker.")

        public_pack = self._public.ensure()
        user = self._users.get_user(command.user_id) or public_pack
        tags = self._effective_tags(command)
        mutation = self._stickers.add_sticker(user, command.reply_sticker_id, tags, public_pack)
        if tags:
            save_effective_pack(self._users, self._public, mutation.effective_pack, public_pack)
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
