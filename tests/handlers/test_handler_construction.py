"""Handlers use the dispatcher only to register callbacks during construction.

Registration order and callback behavior are covered per handler next to each command flow.
This module pins the construction contract shared by every handler: once registered, a
handler keeps its injected application collaborators but no reference to the dispatcher.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.handlers.inline import InlineHandler
from bot.handlers.stickers import StickerHandler
from bot.handlers.utility import HelperHandler, UserHandler
from tests.handlers.support import FakeDispatcher

HANDLERS = {
  "helper": (HelperHandler, 2),
  "user": (UserHandler, 3),
  "sticker": (StickerHandler, 3),
  "inline": (InlineHandler, 2),
}


@pytest.mark.parametrize(("handler_type", "collaborators"), HANDLERS.values(), ids=HANDLERS)
def test_handler_registers_callbacks_without_retaining_the_dispatcher(
  handler_type: type, collaborators: int
) -> None:
  """The dispatcher receives the callbacks; the handler instance does not keep it."""
  dispatcher = FakeDispatcher()

  handler = handler_type(dispatcher, *(MagicMock() for _ in range(collaborators)))

  assert dispatcher.handlers
  assert all(value is not dispatcher for value in vars(handler).values())
