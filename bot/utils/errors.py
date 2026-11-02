# SPDX-License-Identifier: BSD-2-Clause

"""Exceptions raised and handled inside the Telegram adapters.

These are adapter control flow, not application errors: the ``bot.utils.messages`` checks reply to
the user first and then raise one of them so the handler stops processing; handlers catch them and
only log. Application failures use ``stickfix_application.errors`` instead. Keep new adapter-only
failures here until Milestone 4.5 moves them next to the handlers that raise them.
"""

import logging


class StickfixException(Exception):
  """Base class for adapter exceptions that carry a log message and its cause.

  Attributes:
      message: Text logged when the exception is raised (``err_message`` argument).
      cause: Why it was raised (``err_cause`` argument); ``"UNKNOWN."`` when omitted.
  """

  def __init__(self, err_message="", err_cause=None):
    self.message = err_message
    self.cause = err_cause if err_cause is not None else "UNKNOWN."


class InputException(StickfixException):
  """Raised when a command's arguments are malformed."""


class NoStickerException(StickfixException):
  """Raised when a command must reply to a sticker but the replied-to message has none."""


class WrongContextException(StickfixException):
  """Raised when a command runs in the wrong chat context.

  For example, a command restricted to private chats that is called from a group chat.
  """


class InsufficientPermissionsException(StickfixException):
  """Raised when a user calls a command without the required permissions."""


class DatabaseException(StickfixException):
  """Raised when a database operation fails."""


# Keep the historical misspelling importable for callers outside the bot.
# cspell:disable-next-line
Databasexception = DatabaseException


def unexpected_error(e: Exception, a_logger: logging.Logger):
  """Log an exception a handler did not expect, at CRITICAL level, without re-raising it.

  Handlers call this from their catch-all branch so a failing update never stops polling; the
  inline-query handler re-raises afterwards so PTB's error handling still sees the failure.
  """
  a_logger.critical("Unexpected error")
  a_logger.critical(str(type(e)))
  a_logger.critical(str(e.args))
