"""Use case for clearing inline-query sticker caches."""

from __future__ import annotations

from bot.application.requests import ClearInlineCacheCommand
from bot.application.results import AcknowledgementResult

from ._base import StickerPackUseCase
from ._repositories import resolve_effective_user, save_effective_pack


class ClearInlineCache(StickerPackUseCase):
    """Drop the cached-sticker list from whichever pack served the inline query.

    Telegram fires ``chosen_inline_result`` after a user picks a sticker; the
    handler calls this to invalidate the per-owner cache so the next inline query
    is recomputed. The owner is the caller's private pack when they are in private
    mode, otherwise the shared public pack (see :func:`resolve_effective_user` and
    ``StickerPackService.resolve_effective_pack``).
    """

    def __call__(self, command: ClearInlineCacheCommand) -> AcknowledgementResult:
        public_pack = self._public.get()
        user = resolve_effective_user(self._users, command.user_id, public_pack)
        cache_owner = self._stickers.resolve_effective_pack(user, public_pack)
        cache_owner.remove_cached_stickers()
        save_effective_pack(self._users, self._public, cache_owner, public_pack)
        return AcknowledgementResult(acknowledged=True)
