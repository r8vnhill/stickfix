"""Package-level export surface for application-layer contracts.

This module re-exports commonly used application errors, DTOs, and selected results so callers can
import from one stable namespace when needed.

## Contract:

- keep exports Telegram-free (validated by seam tests that import ``bot.application``)
- treat ``__all__`` as the supported package-level API for compatibility
- avoid business logic here; implementation lives in submodules such as ``requests``, ``results``,
  ``errors``, and ``use_cases``

## Integration points:

- application seam tests import this package directly
- handlers and use-case tests usually import specific submodules
"""

from .errors import (
    ApplicationError,
    InvalidCommandInputError,
    MissingReplyStickerError,
    MissingStickerError,
    UserNotFoundError,
    WrongInteractionContextError,
)
from .requests import (
    AddStickerCommand,
    ClearInlineCacheCommand,
    DeleteStickerCommand,
    DeleteUserCommand,
    GetStickersQuery,
    InlineQueryRequest,
    SetModeCommand,
    SetShuffleCommand,
)
from .results import AcknowledgementResult, GetStickersResult, InlineQueryResult
from .use_cases import ClearInlineCache

__all__ = [
    "AcknowledgementResult",
    "AddStickerCommand",
    "ApplicationError",
    "ClearInlineCache",
    "ClearInlineCacheCommand",
    "DeleteStickerCommand",
    "DeleteUserCommand",
    "GetStickersQuery",
    "GetStickersResult",
    "InlineQueryRequest",
    "InlineQueryResult",
    "InvalidCommandInputError",
    "MissingReplyStickerError",
    "MissingStickerError",
    "SetModeCommand",
    "SetShuffleCommand",
    "UserNotFoundError",
    "WrongInteractionContextError",
]
