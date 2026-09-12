"""Use case for retrieving stickers by tag."""

from __future__ import annotations

from bot.application.errors import WrongInteractionContextError
from bot.application.requests import GetStickersQuery, InteractionScope
from bot.application.results import GetStickersResult

from ._base import StickerPackUseCase
from ._repositories import resolve_effective_user


class GetStickers(StickerPackUseCase):
  """Resolve the sticker ids a private-chat ``/get <tags>`` should reply with.

  ``/get`` is private-chat only: a non-private ``interaction_scope`` raises
  :class:`WrongInteractionContextError` and the handler turns that into a user
  message. This use case never mutates state -- it only reads the effective
  pack -- so, unlike the add/delete cases, it performs no save.
  """

  def __call__(self, query: GetStickersQuery) -> GetStickersResult:
    if query.interaction_scope is not InteractionScope.PRIVATE:
      raise WrongInteractionContextError("The /get command only works in private chats.")

    public_pack = self._public.get()
    user = resolve_effective_user(self._users, query.user_id, public_pack)

    sticker_ids = self._stickers.find_stickers(user, query.tags, public_pack)
    return GetStickersResult(sticker_ids=sticker_ids)
