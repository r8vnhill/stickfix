"""Sticker-pack behavior that is independent from Telegram and persistence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Sequence

from bot.domain.user import StickfixUser


@dataclass(frozen=True, slots=True)
class StickerPackMutation:
    """Outcome of mutating one effective sticker pack."""

    effective_pack: StickfixUser
    changed: bool


class StickerPackService:
    """Resolve and mutate the effective sticker pack for a user."""

    def resolve_effective_pack(
        self,
        user: StickfixUser,
        public_pack: StickfixUser | None = None,
    ) -> StickfixUser:
        return user.get_effective_pack(public_user=public_pack)

    def add_sticker(
        self,
        user: StickfixUser,
        sticker_id: str,
        tags: Sequence[str],
        public_pack: StickfixUser | None = None,
    ) -> StickerPackMutation:
        effective_pack = self.resolve_effective_pack(user, public_pack)
        before = deepcopy(effective_pack.stickers)
        if tags:
            user.link_sticker(
                sticker_id=sticker_id,
                sticker_tags=list(tags),
                public_user=public_pack,
            )
        return StickerPackMutation(effective_pack, before != effective_pack.stickers)

    def delete_sticker(
        self,
        user: StickfixUser,
        sticker_id: str,
        tags: Sequence[str],
        public_pack: StickfixUser | None = None,
    ) -> StickerPackMutation:
        effective_pack = self.resolve_effective_pack(user, public_pack)
        before = deepcopy(effective_pack.stickers)
        user.unlink_sticker_from_pack(
            sticker_id=sticker_id,
            sticker_tags=list(tags),
            public_user=public_pack,
        )
        return StickerPackMutation(effective_pack, before != effective_pack.stickers)

    def find_stickers(
        self,
        user: StickfixUser,
        tags: Sequence[str],
        public_pack: StickfixUser | None = None,
    ) -> tuple[str, ...]:
        return tuple(user.get_shuffled_sticker_list(list(tags), public_user=public_pack))
