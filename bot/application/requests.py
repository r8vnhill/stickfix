"""Transport-agnostic request DTOs for application use cases."""

from __future__ import annotations

from dataclasses import dataclass, field

from bot.domain.user import Switch, UserModes


@dataclass(frozen=True, slots=True)
class AddStickerCommand:
    user_id: str
    chat_id: str
    chat_type: str
    reply_sticker_id: str | None
    reply_sticker_emoji: str | None
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class GetStickersQuery:
    user_id: str
    chat_id: str
    chat_type: str
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DeleteStickerCommand:
    user_id: str
    chat_id: str
    chat_type: str
    reply_sticker_id: str | None
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SetModeCommand:
    user_id: str
    mode: UserModes | str


@dataclass(frozen=True, slots=True)
class SetShuffleCommand:
    user_id: str
    shuffle: Switch | str


@dataclass(frozen=True, slots=True)
class DeleteUserCommand:
    user_id: str


@dataclass(frozen=True, slots=True)
class InlineQueryRequest:
    user_id: str | None
    query_text: str
    offset: int = 0
    limit: int = 49


@dataclass(frozen=True, slots=True)
class ClearInlineCacheCommand:
    user_id: str
    query_text: str = ""
