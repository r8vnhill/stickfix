"""Immutable result DTOs returned by application use cases.

The DTOs contain only values that adapters need to render replies, send
stickers, or continue inline pagination. Their frozen, slotted shape is part of
the application contract and keeps transport-specific concerns out of this
package.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AcknowledgementResult:
  acknowledged: bool = True
  detail: str | None = None


@dataclass(frozen=True, slots=True)
class AddStickerResult:
  sticker_id: str
  effective_tags: tuple[str, ...] = field(default_factory=tuple)
  changed: bool = False


@dataclass(frozen=True, slots=True)
class DeleteStickerResult:
  sticker_id: str
  effective_tags: tuple[str, ...] = field(default_factory=tuple)
  changed: bool = False


@dataclass(frozen=True, slots=True)
class GetStickersResult:
  sticker_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class InlineQueryResult:
  sticker_ids: tuple[str, ...] = field(default_factory=tuple)
  default_tags: tuple[str, ...] = field(default_factory=tuple)
  show_default_help: bool = False
  help_text: str | None = None
  next_offset: int = 0
  cache_cleared: bool = False
