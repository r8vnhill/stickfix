"""Application use cases: Telegram-free business logic.

This package contains callable use case classes that encapsulate user-facing
commands and flows (e.g., changing mode, adding stickers, retrieving stickers).
Use cases accept transport-agnostic request DTOs and return result/error types,
allowing Telegram handlers to remain thin adapters.

Handlers instantiate use cases with infrastructure dependencies (e.g., user
repository) and invoke them with parsed command data. Tests import and invoke
use cases with in-memory fakes, achieving testability independent of Telegram.
"""

from .set_mode import SetMode

__all__ = ["SetMode"]
