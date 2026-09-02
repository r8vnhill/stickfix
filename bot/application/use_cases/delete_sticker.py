"""Use case for removing a sticker from the effective sticker pack."""

from __future__ import annotations

import logging

from bot.application.errors import MissingStickerError
from bot.application.requests import DeleteStickerCommand
from bot.application.results import DeleteStickerResult

from ._base import StickerPackUseCase
from ._repositories import resolve_effective_user, save_effective_pack

logger = logging.getLogger(__name__)


class DeleteSticker(StickerPackUseCase):
    """Unlink a sticker (optionally only from given tags) from the effective pack.

    With no ``tags`` the sticker is removed entirely; with tags it is only
    detached from those tags. The effective pack is always saved afterwards so a
    no-op delete still round-trips cleanly. Raises :class:`MissingStickerError`
    when the command carries no sticker id. Tagged removals emit an operational
    INFO record after the repository mutation succeeds.
    """

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
        _log_tag_removal(command)
        return DeleteStickerResult(
            sticker_id=command.reply_sticker_id,
            effective_tags=command.tags,
            changed=mutation.changed,
        )


def _log_tag_removal(command: DeleteStickerCommand) -> None:
    if command.tags:
        logger.info(
            "Removed sticker %s from tags %s",
            command.reply_sticker_id,
            ", ".join(command.tags),
        )
