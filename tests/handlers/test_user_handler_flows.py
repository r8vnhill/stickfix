from __future__ import annotations

from types import SimpleNamespace

from hamcrest import assert_that, equal_to
from telegram.ext import CommandHandler

from bot.application.requests import DeleteUserCommand, EnsureUserCommand, SetShuffleCommand
from bot.application.results import AcknowledgementResult
from bot.handlers.utility import HelperHandler, UserHandler
from bot.utils.messages import Commands
from tests.handlers.support import FakeDispatcher, command_callback


class FakeMessage:
  def __init__(self) -> None:
    self.from_user = SimpleNamespace(username="alice", id=123)
    self.text_replies: list[str] = []

  def reply_text(self, text: str) -> None:
    self.text_replies.append(text)


class FakeBot:
  def __init__(self) -> None:
    self.sent_stickers: list[tuple[int, str]] = []
    self.sent_messages: list[dict[str, object]] = []

  def send_sticker(self, chat_id: int, sticker: str) -> None:
    self.sent_stickers.append((chat_id, sticker))

  def send_message(self, **kwargs: object) -> None:
    self.sent_messages.append(kwargs)


def make_update(message: FakeMessage | None = None):
  return SimpleNamespace(
    effective_message=message or FakeMessage(),
    effective_user=SimpleNamespace(id=123, username="alice"),
    effective_chat=SimpleNamespace(id=456, type="private", username="alice"),
  )


class RecordingUseCase:
  def __init__(self, result=None) -> None:
    self.commands = []
    self.result = result

  def __call__(self, command):
    self.commands.append(command)
    return self.result


class FakeGetHelp:
  def __init__(self, content: str) -> None:
    self.content = content

  def __call__(self) -> str:
    return self.content


def test_start_handler_sends_greeting_and_ensures_numeric_user() -> None:
  ensure = RecordingUseCase(AcknowledgementResult())
  dispatcher = FakeDispatcher()
  HelperHandler(dispatcher, ensure, RecordingUseCase("help"))
  bot = FakeBot()

  command_callback(dispatcher, Commands.START.value)(make_update(), SimpleNamespace(bot=bot))

  assert_that(ensure.commands, equal_to([EnsureUserCommand(123)]))
  assert_that(bot.sent_stickers, equal_to([(456, "CAADBAADTAADqAABTgXzVqN6dJUIXwI")]))


def test_shuffle_handler_forwards_first_argument() -> None:
  shuffle = RecordingUseCase(AcknowledgementResult())
  dispatcher = FakeDispatcher()
  UserHandler(dispatcher, RecordingUseCase(), shuffle, RecordingUseCase(AcknowledgementResult()))
  message = FakeMessage()

  command_callback(dispatcher, Commands.SHUFFLE.value)(
    make_update(message), SimpleNamespace(args=["on", "ignored"])
  )

  assert_that(shuffle.commands, equal_to([SetShuffleCommand(123, "on")]))
  assert_that(message.text_replies, equal_to(["Done"]))


def test_delete_me_handler_replies_only_when_use_case_acknowledges() -> None:
  delete = RecordingUseCase(AcknowledgementResult(acknowledged=True))
  dispatcher = FakeDispatcher()
  UserHandler(dispatcher, RecordingUseCase(), RecordingUseCase(), delete)
  message = FakeMessage()

  command_callback(dispatcher, Commands.DELETE_ME.value)(make_update(message), SimpleNamespace())

  assert_that(delete.commands, equal_to([DeleteUserCommand(123)]))
  assert_that(message.text_replies, equal_to(["Sure!"]))


def test_help_adapter_sends_provider_content_without_file_io() -> None:
  bot = FakeBot()
  dispatcher = FakeDispatcher()
  HelperHandler(dispatcher, RecordingUseCase(), FakeGetHelp("exact help"))

  command_callback(dispatcher, Commands.HELP.value)(make_update(), SimpleNamespace(bot=bot))

  assert_that(
    bot.sent_messages,
    equal_to(
      [
        {
          "chat_id": 456,
          "text": "exact help",
          "parse_mode": "Markdown",
        }
      ]
    ),
  )


def test_helper_handler_registers_start_then_help() -> None:
  dispatcher = FakeDispatcher()

  HelperHandler(dispatcher, RecordingUseCase(), FakeGetHelp("help"))

  assert_that(
    [handler.command for handler in dispatcher.handlers if isinstance(handler, CommandHandler)],
    equal_to([[Commands.START.value], [Commands.HELP.value]]),
  )


def test_user_handler_registers_delete_me_set_mode_then_shuffle() -> None:
  dispatcher = FakeDispatcher()

  UserHandler(dispatcher, RecordingUseCase(), RecordingUseCase(), RecordingUseCase())

  assert_that(
    [handler.command for handler in dispatcher.handlers if isinstance(handler, CommandHandler)],
    equal_to(
      [
        [Commands.DELETE_ME.value.lower()],
        [Commands.SET_MODE.value.lower()],
        [Commands.SHUFFLE.value],
      ]
    ),
  )
