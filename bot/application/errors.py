"""Application-specific error types."""

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
