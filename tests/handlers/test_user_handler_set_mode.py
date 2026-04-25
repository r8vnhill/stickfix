from __future__ import annotations

from types import SimpleNamespace

from hamcrest import assert_that, empty, equal_to

from bot.application.errors import InvalidCommandInputError
from bot.application.requests import SetModeCommand
from bot.handlers.utility import UserHandler


class FakeDispatcher:
    def __init__(self) -> None:
        self.handlers = []

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)


class FakeUseCase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[SetModeCommand] = []

    def __call__(self, command: SetModeCommand) -> None:
        self.commands.append(command)
        if self.error is not None:
            raise self.error


class FakeMessage:
    def __init__(self) -> None:
        self.text_replies: list[str] = []
        self.markdown_replies: list[str] = []

    def reply_text(self, text: str) -> None:
        self.text_replies.append(text)

    def reply_markdown(self, text: str) -> None:
        self.markdown_replies.append(text)


def make_handler(use_case: FakeUseCase) -> UserHandler:
    handler = UserHandler(FakeDispatcher(), {})
    handler._UserHandler__set_mode_use_case = use_case
    return handler


def make_update(message: FakeMessage):
    return SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=123, username="alice"),
        effective_chat=SimpleNamespace(id=456),
    )


def call_set_mode(handler: UserHandler, update, args: list[str]) -> None:
    context = SimpleNamespace(args=args)
    handler._UserHandler__set_mode(update, context)


def test_set_mode_handler_sends_first_argument_to_use_case() -> None:
    use_case = FakeUseCase()
    handler = make_handler(use_case)
    message = FakeMessage()

    call_set_mode(handler, make_update(message), ["private", "ignored"])

    assert_that(use_case.commands, equal_to([SetModeCommand(user_id=123, mode="private")]))
    assert_that(message.text_replies, equal_to(["Leave it to me!"]))
    assert_that(message.markdown_replies, empty())


def test_set_mode_handler_maps_invalid_input_to_existing_markdown_reply() -> None:
    use_case = FakeUseCase(InvalidCommandInputError())
    handler = make_handler(use_case)
    message = FakeMessage()

    call_set_mode(handler, make_update(message), ["invalid"])

    assert_that(message.text_replies, empty())
    assert_that(message.markdown_replies, equal_to([
        "Sorry, I didn't understand. This command syntax is `/setMode private` "
        "or `setMode public`."
    ]))


def test_set_mode_handler_keeps_missing_argument_noop() -> None:
    use_case = FakeUseCase()
    handler = make_handler(use_case)
    message = FakeMessage()

    call_set_mode(handler, make_update(message), [])

    assert_that(use_case.commands, empty())
    assert_that(message.text_replies, empty())
    assert_that(message.markdown_replies, empty())
