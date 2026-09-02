"""Shared constructor plumbing for pack-oriented use cases.

``AddSticker``, ``DeleteSticker``, ``GetStickers``, ``ClearInlineCache`` and
``ResolveInlineQuery`` all need the same three collaborators and wire them the
same way. ``StickerPackUseCase`` owns that wiring so each use case only has to
implement its own ``__call__``; keeping it here also guarantees the collaborator
set stays identical across every pack use case.
"""

from __future__ import annotations

from bot.application.ports import PublicPackRepository, UserRepository
from bot.domain.services import StickerPackService


class StickerPackUseCase:
    """Base class holding the collaborators every sticker-pack use case needs.

    Args:
        users: Port used to load and persist regular (numeric) users.
        public: Port for the single shared ``SF-PUBLIC`` pack.
        stickers: Domain service that performs the pack mutations/queries. A
            fresh :class:`StickerPackService` is created when omitted so callers
            (and tests) can rely on a stateless default.
    """

    def __init__(
        self,
        users: UserRepository,
        public: PublicPackRepository,
        stickers: StickerPackService | None = None,
    ) -> None:
        self._users = users
        self._public = public
        self._stickers = stickers or StickerPackService()
