"""Application-layer contracts for Stickfix.

This package defines the application layer in hexagonal architecture:

    Handlers (bot/handlers/)
        ↓ parse Telegram, build request DTOs
    Use Cases (bot/application/use_cases/)
        ↓ implement business logic, depend on ports
    Ports (bot/application/ports/)
        ↓ abstract contracts for infrastructure
    Infrastructure Adapters (bot/infrastructure/)
        ↓ concrete implementations (YAML, database, etc.)

Key responsibilities:
  - Use cases: Stateless request/response handlers that implement business rules
  - Ports: Protocol-based interfaces that use cases depend on
  - Errors: Application-specific exceptions with Telegram-free contexts
  - DTOs: Request and result types that cross the handler/application boundary

Constraints:
  - Application must not import telegram or Telegram-specific types
  - Domain layer (bot/domain/) must not import application or handlers
  - Handlers may import all layers but only call use cases via DTOs

This separation enables:
  - Testing use cases without Telegram objects
  - Replacing storage backends by swapping adapters
  - Reusing application logic for multiple interfaces (CLI, API, webhooks, etc.)
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

__all__ = [
    "AcknowledgementResult",
    "AddStickerCommand",
    "ApplicationError",
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
