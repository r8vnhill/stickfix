"""Typed failures raised by transport-agnostic application use cases.

Telegram adapters translate these errors into user-facing responses. The
application package does not know which transport or infrastructure adapter
will perform that translation.
"""

from __future__ import annotations


class ApplicationError(Exception):
  """Base class for application-layer failures."""


class InvalidCommandInputError(ApplicationError):
  """Raised when a command carries invalid arguments."""


class WrongInteractionContextError(ApplicationError):
  """Raised when a command is used in a disallowed interaction context."""


class MissingStickerError(ApplicationError):
  """Raised when a required sticker payload is absent."""


class MissingReplyStickerError(ApplicationError):
  """Raised when a command requires a replied sticker message."""


class UserNotFoundError(ApplicationError):
  """Raised when an operation requires a user that does not exist."""
