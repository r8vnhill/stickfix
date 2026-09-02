from __future__ import annotations

from types import SimpleNamespace

from hamcrest import assert_that, equal_to

from bot.application.requests import DeleteUserCommand, EnsureUserCommand, SetShuffleCommand
from bot.application.results import AcknowledgementResult
from bot.handlers.utility import HelperHandler, UserHandler, send_help_message


class FakeDispatcher:
    def __init__(self) -> None:
        self.handlers = []

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)


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
    handler = HelperHandler(FakeDispatcher(), ensure, RecordingUseCase("help"))
    bot = FakeBot()

    handler._HelperHandler__send_hello_message(make_update(), SimpleNamespace(bot=bot))

    assert_that(ensure.commands, equal_to([EnsureUserCommand(123)]))
    assert_that(bot.sent_stickers, equal_to([(456, "CAADBAADTAADqAABTgXzVqN6dJUIXwI")]))


def test_shuffle_handler_forwards_first_argument() -> None:
    shuffle = RecordingUseCase(AcknowledgementResult())
    handler = UserHandler(
        FakeDispatcher(), RecordingUseCase(), shuffle, RecordingUseCase(AcknowledgementResult())
    )
    message = FakeMessage()

    handler._UserHandler__set_shuffle(make_update(message), SimpleNamespace(args=["on", "ignored"]))

    assert_that(shuffle.commands, equal_to([SetShuffleCommand(123, "on")]))
    assert_that(message.text_replies, equal_to(["Done"]))


def test_delete_me_handler_replies_only_when_use_case_acknowledges() -> None:
    delete = RecordingUseCase(AcknowledgementResult(acknowledged=True))
    handler = UserHandler(FakeDispatcher(), RecordingUseCase(), RecordingUseCase(), delete)
    message = FakeMessage()

    handler._UserHandler__remove_user(make_update(message), SimpleNamespace())

    assert_that(delete.commands, equal_to([DeleteUserCommand(123)]))
    assert_that(message.text_replies, equal_to(["Sure!"]))


def test_help_adapter_sends_provider_content_without_file_io() -> None:
    bot = FakeBot()
    update = make_update()

    send_help_message(update, SimpleNamespace(bot=bot), FakeGetHelp("exact help"))

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
