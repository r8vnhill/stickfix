"""Map normalized PostgreSQL rows to the Telegram-free domain aggregate.

The mapper is intentionally one-way in this module: repository write paths
construct rows directly, while these functions rebuild ordered sticker and
cache associations for application reads.
"""

from __future__ import annotations

from collections.abc import Iterable

from stickfix_domain import SF_PUBLIC, StickfixUser, UserId

from .models import (
  PublicCachedStickerRow,
  PublicStickerTagRow,
  UserCachedStickerRow,
  UserRow,
  UserStickerTagRow,
)


def user_from_rows(
  row: UserRow,
  sticker_rows: Iterable[tuple[UserStickerTagRow, str]],
  cache_rows: Iterable[tuple[UserCachedStickerRow, str]],
) -> StickfixUser:
  user = StickfixUser(UserId(row.telegram_id))
  user.private_mode = row.private_mode
  user.shuffle = row.shuffle
  _apply_stickers(user.stickers, sticker_rows)
  _apply_stickers(user.cached_stickers, cache_rows)
  return user


def public_pack_from_rows(
  sticker_rows: Iterable[tuple[PublicStickerTagRow, str]],
  cache_rows: Iterable[tuple[PublicCachedStickerRow, str]],
) -> StickfixUser:
  pack = StickfixUser(SF_PUBLIC)
  _apply_stickers(pack.stickers, sticker_rows)
  _apply_stickers(pack.cached_stickers, cache_rows)
  return pack


def _apply_stickers(target: dict[str, list[str]], rows: Iterable[tuple[object, str]]) -> None:
  for row, tag in rows:
    sticker_id = row.sticker_id  # type: ignore[attr-defined]
    target.setdefault(tag, []).append(sticker_id)
