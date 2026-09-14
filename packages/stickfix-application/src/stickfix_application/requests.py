"""Transport-agnostic request DTOs for application use cases.

Each use case takes exactly one of these frozen dataclasses as input. They carry
only primitives and domain value objects -- never Telegram ``Update``/``Message``
objects -- so the interface adapters in :mod:`bot.handlers` are responsible for
parsing an update into the right request here. ``frozen=True, slots=True`` keeps
them cheap and hashable and stops a use case from mutating its own input.

Maintainer notes:
    * A field typed ``UserId | None`` means the request can originate from
      anonymous inline traffic; use cases fall back to the public pack in that
      case (see :func:`stickfix_application.use_cases._repositories.resolve_effective_user`).
    * ``InteractionScope`` exists so use cases can enforce "private chat only"
      rules without importing anything Telegram-specific.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from stickfix_domain import Switch, UserId, UserModes


class InteractionScope(str, Enum):
  """Where a command was invoked, as far as application rules care.

  Handlers collapse Telegram's several chat types into just these two: a chat is
  either a 1:1 private chat or it is not.
  """

  PRIVATE = "private"
  NON_PRIVATE = "non_private"


@dataclass(frozen=True, slots=True)
class AddStickerCommand:
  """``/add``: link the replied-to sticker to ``tags`` (emoji used if empty)."""

  user_id: UserId
  reply_sticker_id: str | None
  reply_sticker_emoji: str | None
  tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class GetStickersQuery:
  """``/get``: fetch sticker ids for ``tags``; rejected outside private chats."""

  user_id: UserId
  interaction_scope: InteractionScope
  tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DeleteStickerCommand:
  """``/deleteFrom``: unlink a sticker fully, or only from ``tags`` when given."""

  user_id: UserId
  reply_sticker_id: str | None
  tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SetModeCommand:
  """``/setMode``: switch the caller between private and public packs.

  ``mode`` may arrive as a raw command argument; the use case validates it.
  """

  user_id: UserId
  mode: UserModes | str


@dataclass(frozen=True, slots=True)
class SetShuffleCommand:
  """``/shuffle``: toggle shuffled sticker ordering for the caller."""

  user_id: UserId
  shuffle: Switch | str


@dataclass(frozen=True, slots=True)
class DeleteUserCommand:
  """``/deleteMe``: drop the caller's stored record and private pack."""

  user_id: UserId


@dataclass(frozen=True, slots=True)
class EnsureUserCommand:
  """``/start``: create the caller's record if it does not exist yet."""

  user_id: UserId


@dataclass(frozen=True, slots=True)
class InlineQueryRequest:
  """One inline-query page; ``user_id`` is ``None`` for anonymous queries.

  ``offset``/``limit`` page the results Telegram-style; an empty ``query_text``
  at ``offset == 0`` also asks for the default help article.
  """

  user_id: UserId | None
  query_text: str
  offset: int = 0
  limit: int = 49


@dataclass(frozen=True, slots=True)
class ClearInlineCacheCommand:
  """Invalidate the inline cache after the caller picks a chosen result."""

  user_id: UserId | None
