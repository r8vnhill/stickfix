from __future__ import annotations

from types import SimpleNamespace

from hamcrest import assert_that, equal_to

from bot.application.errors import WrongInteractionContextError
from bot.application.requests import AddStickerCommand, DeleteStickerCommand, GetStickersQuery
from bot.application.results import AddStickerResult, DeleteStickerResult, GetStickersResult
from bot.handlers.stickers import StickerHandler


class FakeDispatcher:
    def __init__(self) -> None:
        self.handlers = []

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)


class FakeMessage:
    def __init__(self, reply_to_message=None) -> None:
        self.reply_to_message = reply_to_message
        self.text_replies: list[str] = []
        self.markdown_replies: list[str] = []
        self.from_user = SimpleNamespace(username="alice")

    def reply_text(self, text: str) -> None:
        self.text_replies.append(text)

    def reply_markdown(self, text: str) -> None:
        self.markdown_replies.append(text)


class FakeChat:
    def __init__(self, chat_id: int = 456, chat_type: str = "private") -> None:
        self.id = chat_id
        self.type = chat_type
        self.sent_stickers: list[str] = []

    def send_sticker(self, sticker_id: str) -> None:
        self.sent_stickers.append(sticker_id)


class FakeAddSticker:
    def __init__(self) -> None:
        self.commands: list[AddStickerCommand] = []

    def __call__(self, command: AddStickerCommand) -> AddStickerResult:
        self.commands.append(command)
        return AddStickerResult(
            sticker_id=command.reply_sticker_id or "",
            effective_tags=command.tags,
        )


class FakeGetStickers:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[GetStickersQuery] = []

    def __call__(self, query: GetStickersQuery) -> GetStickersResult:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return GetStickersResult(sticker_ids=("sticker-a", "sticker-b"))


class FakeDeleteSticker:
    def __init__(self) -> None:
        self.commands: list[DeleteStickerCommand] = []

    def __call__(self, command: DeleteStickerCommand) -> DeleteStickerResult:
        self.commands.append(command)
        return DeleteStickerResult(
            sticker_id=command.reply_sticker_id or "",
            effective_tags=command.tags,
        )


def make_handler(
    add_use_case: FakeAddSticker | None = None,
    get_use_case: FakeGetStickers | None = None,
    delete_use_case: FakeDeleteSticker | None = None,
) -> StickerHandler:
    handler = StickerHandler(FakeDispatcher(), {})
    handler._StickerHandler__add_sticker_use_case = add_use_case or FakeAddSticker()
    handler._StickerHandler__get_stickers_use_case = get_use_case or FakeGetStickers()
    handler._StickerHandler__delete_sticker_use_case = delete_use_case or FakeDeleteSticker()
    return handler


def make_update(message: FakeMessage, chat: FakeChat | None = None):
    return SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=123, username="alice"),
        effective_chat=chat or FakeChat(),
    )


def test_add_handler_builds_command_and_replies_ok() -> None:
    add_use_case = FakeAddSticker()
    handler = make_handler(add_use_case=add_use_case)
    sticker = SimpleNamespace(file_id="sticker-1", emoji="smile")
    message = FakeMessage(reply_to_message=SimpleNamespace(sticker=sticker))

    handler._StickerHandler__add_sticker(make_update(message), SimpleNamespace(args=["wave"]))

    assert_that(add_use_case.commands, equal_to([
        AddStickerCommand(
            user_id=123,
            chat_id=456,
            chat_type="private",
            reply_sticker_id="sticker-1",
            reply_sticker_emoji="smile",
            tags=("wave",),
        )
    ]))
    assert_that(message.text_replies, equal_to(["Ok!"]))


def test_get_handler_builds_query_and_sends_returned_stickers() -> None:
    get_use_case = FakeGetStickers()
    handler = make_handler(get_use_case=get_use_case)
    message = FakeMessage()
    chat = FakeChat()

    handler._StickerHandler__get_stickers(
        make_update(message, chat),
        SimpleNamespace(args=["wave"]),
    )

    assert_that(get_use_case.queries, equal_to([
        GetStickersQuery(user_id=123, chat_id=456, chat_type="private", tags=("wave",))
    ]))
    assert_that(chat.sent_stickers, equal_to(["sticker-a", "sticker-b"]))


def test_get_handler_maps_wrong_context_to_existing_reply() -> None:
    get_use_case = FakeGetStickers(WrongInteractionContextError())
    handler = make_handler(get_use_case=get_use_case)
    message = FakeMessage()
    chat = FakeChat(chat_type="group")

    handler._StickerHandler__get_stickers(
        make_update(message, chat),
        SimpleNamespace(args=["wave"]),
    )

    assert_that(message.text_replies, equal_to(["This command only works in private chats."]))
    assert_that(chat.sent_stickers, equal_to([]))


def test_delete_handler_builds_command_and_stays_silent_on_success() -> None:
    delete_use_case = FakeDeleteSticker()
    handler = make_handler(delete_use_case=delete_use_case)
    sticker = SimpleNamespace(file_id="sticker-1", emoji="smile")
    message = FakeMessage(reply_to_message=SimpleNamespace(sticker=sticker))

    handler._StickerHandler__delete_from(make_update(message), SimpleNamespace(args=["wave"]))

    assert_that(delete_use_case.commands, equal_to([
        DeleteStickerCommand(
            user_id=123,
            chat_id=456,
            chat_type="private",
            reply_sticker_id="sticker-1",
            tags=("wave",),
        )
    ]))
    assert_that(message.text_replies, equal_to([]))
    assert_that(message.markdown_replies, equal_to([]))
