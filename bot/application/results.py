"""Application result DTOs for Phase 2 use cases."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AcknowledgementResult:
    acknowledged: bool = True
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class GetStickersResult:
    sticker_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class InlineQueryResult:
    sticker_ids: tuple[str, ...] = field(default_factory=tuple)
    default_tags: tuple[str, ...] = field(default_factory=tuple)
    show_default_help: bool = False
    next_offset: int = 0
    cache_cleared: bool = False
