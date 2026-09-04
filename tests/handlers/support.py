"""Shared fakes and helpers for exercising registered Telegram handler callbacks.

Handler tests build a ``FakeDispatcher``, construct the handler under test against it, and
then look up the callback the handler registered for a given command or update type. Testing
through this public seam — rather than calling private handler methods directly — keeps tests
coupled to the same contract Telegram itself relies on.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from telegram.ext import (
    ChosenInlineResultHandler,
    CommandHandler,
    InlineQueryHandler,
)


class FakeDispatcher:
    """Minimal stand-in for python-telegram-bot's ``Dispatcher``.

    Records every handler passed to :meth:`add_handler` in registration order, which is all
    the handler constructors under test need to attach their callbacks.
    """

    def __init__(self) -> None:
        self.handlers: list[Any] = []

    def add_handler(self, handler: Any) -> None:
        self.handlers.append(handler)


def command_callback(dispatcher: Any, command: str) -> Callable[..., Any]:
    """Return the callback registered for one Telegram command."""
    handlers = [
        handler
        for handler in dispatcher.handlers
        if isinstance(handler, CommandHandler)
        and str(command).casefold()
        in {str(registered).casefold() for registered in handler.command}
    ]
    if len(handlers) != 1:
        raise AssertionError(f"Expected one handler for /{command}, found {len(handlers)}")
    return handlers[0].callback


def inline_query_callback(dispatcher: Any) -> Callable[..., Any]:
    """Return the callback registered for inline queries."""
    return _single_callback(dispatcher, InlineQueryHandler)


def chosen_result_callback(dispatcher: Any) -> Callable[..., Any]:
    """Return the callback registered for chosen inline results."""
    return _single_callback(dispatcher, ChosenInlineResultHandler)


def _single_callback(dispatcher: Any, handler_type: type) -> Callable[..., Any]:
    handlers = [handler for handler in dispatcher.handlers if isinstance(handler, handler_type)]
    if len(handlers) != 1:
        raise AssertionError(f"Expected one {handler_type.__name__}, found {len(handlers)}")
    return handlers[0].callback
