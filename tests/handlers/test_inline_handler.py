from __future__ import annotations

from dataclasses import dataclass

import pytest
from hamcrest import assert_that, empty, equal_to, has_length, instance_of, is_
from telegram import InlineQueryResultArticle, InlineQueryResultCachedSticker, ParseMode
from telegram.ext import ChosenInlineResultHandler, InlineQueryHandler

from bot.application.requests import ClearInlineCacheCommand, InlineQueryRequest
from bot.application.results import AcknowledgementResult, InlineQueryResult
from bot.handlers.inline import InlineHandler
from tests.handlers.support import FakeDispatcher, chosen_result_callback, inline_query_callback


class FakeBot:
    def __init__(self) -> None:
        self.answer_inline_query_calls: list[dict[str, object]] = []

    def answer_inline_query(self, *args: object, **kwargs: object) -> None:
        self.answer_inline_query_calls.append({"args": args, "kwargs": kwargs})


class FakeResolveInlineQuery:
    """Fake resolver returning a controlled application result."""

    def __init__(self, result: InlineQueryResult | None = None) -> None:
        self.calls: list[InlineQueryRequest] = []
        self.result = result or InlineQueryResult(
            sticker_ids=(),
            default_tags=(),
            show_default_help=False,
            help_text=None,
            next_offset=0,
        )

    def __call__(self, request: InlineQueryRequest) -> InlineQueryResult:
        self.calls.append(request)
        return self.result


class FakeClearInlineCache:
    """Fake cache clearer recording application commands."""

    def __init__(self) -> None:
        self.calls: list[ClearInlineCacheCommand] = []

    def __call__(self, command: ClearInlineCacheCommand) -> AcknowledgementResult:
        self.calls.append(command)
        return AcknowledgementResult(acknowledged=True)


@dataclass
class FakeContext:
    bot: FakeBot


@dataclass
class FakeTelegramUser:
    id: int


@dataclass
class FakeInlineQuery:
    id: str
    query: str
    offset: str = "0"


@dataclass
class FakeChosenInlineResult:
    query: str


@dataclass
class FakeUpdate:
    effective_user: FakeTelegramUser | None
    inline_query: FakeInlineQuery | None = None
    chosen_inline_result: FakeChosenInlineResult | None = None


def make_handler(
    resolve_inline_query: FakeResolveInlineQuery | None = None,
    clear_inline_cache: FakeClearInlineCache | None = None,
) -> FakeDispatcher:
    dispatcher = FakeDispatcher()
    InlineHandler(
        dispatcher,
        resolve_inline_query or FakeResolveInlineQuery(),
        clear_inline_cache or FakeClearInlineCache(),
    )
    return dispatcher


def call_inline_get(
    dispatcher: FakeDispatcher,
    bot: FakeBot,
    *,
    user_id: int | None = 123,
    query: str = "wave",
    offset: str = "0",
    inline_query_id: str = "inline-1",
) -> None:
    update = FakeUpdate(
        effective_user=FakeTelegramUser(user_id) if user_id is not None else None,
        inline_query=FakeInlineQuery(id=inline_query_id, query=query, offset=offset),
    )
    inline_query_callback(dispatcher)(update, FakeContext(bot=bot))


def call_chosen_result(
    dispatcher: FakeDispatcher,
    bot: FakeBot,
    *,
    user_id: int | None = 123,
    query: str = "wave",
) -> None:
    update = FakeUpdate(
        effective_user=FakeTelegramUser(user_id) if user_id is not None else None,
        chosen_inline_result=FakeChosenInlineResult(query=query),
    )
    chosen_result_callback(dispatcher)(update, FakeContext(bot=bot))


def returned_results(bot: FakeBot) -> list[object]:
    call = bot.answer_inline_query_calls[0]
    return list(call["args"][1])


def assert_answer_arguments(
    bot: FakeBot,
    *,
    inline_query_id: str = "inline-1",
    next_offset: str = "49",
) -> None:
    call = bot.answer_inline_query_calls[0]
    assert_that(call["args"][0], equal_to(inline_query_id))
    assert_that(call["kwargs"]["cache_time"], equal_to(1))
    assert_that(call["kwargs"]["is_personal"], is_(True))
    assert_that(call["kwargs"]["next_offset"], equal_to(next_offset))


def test_inline_handler_registers_handlers_in_current_order() -> None:
    dispatcher = make_handler()

    assert_that(dispatcher.handlers, has_length(2))
    assert_that(dispatcher.handlers[0], instance_of(InlineQueryHandler))
    assert_that(dispatcher.handlers[1], instance_of(ChosenInlineResultHandler))
    assert_that(callable(inline_query_callback(dispatcher)), is_(True))
    assert_that(callable(chosen_result_callback(dispatcher)), is_(True))


def test_empty_inline_query_renders_application_help_before_stickers() -> None:
    resolver = FakeResolveInlineQuery(
        InlineQueryResult(
            sticker_ids=("empty-query-sticker",),
            default_tags=("wave",),
            show_default_help=True,
            help_text="help text",
            next_offset=49,
        )
    )
    dispatcher = make_handler(resolve_inline_query=resolver)
    bot = FakeBot()

    call_inline_get(dispatcher, bot, query="")

    results = returned_results(bot)
    assert_that(results[0], instance_of(InlineQueryResultArticle))
    assert_that(results[0].title, equal_to("Click me for help"))
    assert_that(results[0].description, equal_to("Try calling me inline like `@stickfixbot wave`"))
    assert_that(results[0].input_message_content.parse_mode, equal_to(ParseMode.MARKDOWN))
    assert_that(results[1], instance_of(InlineQueryResultCachedSticker))
    assert_that(results[1].sticker_file_id, equal_to("empty-query-sticker"))
    assert_answer_arguments(bot)


def test_inline_query_renders_application_sticker_ids_without_help_article() -> None:
    resolver = FakeResolveInlineQuery(
        InlineQueryResult(
            sticker_ids=("sticker-a", "sticker-b"),
            default_tags=(),
            show_default_help=False,
            help_text=None,
            next_offset=49,
        )
    )
    dispatcher = make_handler(resolve_inline_query=resolver)
    bot = FakeBot()

    call_inline_get(dispatcher, bot)

    results = returned_results(bot)
    assert_that(results, has_length(2))
    assert_that(
        all(isinstance(result, InlineQueryResultCachedSticker) for result in results), is_(True)
    )
    assert_that(
        tuple(result.sticker_file_id for result in results),
        equal_to(("sticker-a", "sticker-b")),
    )
    assert_answer_arguments(bot)


def test_invalid_inline_query_offset_raises_before_answering() -> None:
    resolver = FakeResolveInlineQuery()
    dispatcher = make_handler(resolve_inline_query=resolver)
    bot = FakeBot()

    with pytest.raises(ValueError):
        call_inline_get(dispatcher, bot, offset="not-an-int")

    assert_that(resolver.calls, empty())
    assert_that(bot.answer_inline_query_calls, empty())


def test_inline_query_builds_request_with_user_id_when_effective_user_exists() -> None:
    resolver = FakeResolveInlineQuery()
    dispatcher = make_handler(resolve_inline_query=resolver)
    bot = FakeBot()

    call_inline_get(dispatcher, bot, user_id=456, query="search")

    assert_that(resolver.calls, has_length(1))
    assert_that(resolver.calls[0].user_id, equal_to(456))


def test_inline_query_builds_request_with_none_user_id_when_effective_user_is_none() -> None:
    resolver = FakeResolveInlineQuery()
    dispatcher = make_handler(resolve_inline_query=resolver)
    bot = FakeBot()

    call_inline_get(dispatcher, bot, user_id=None, query="search")

    assert_that(resolver.calls, has_length(1))
    assert_that(resolver.calls[0].user_id, equal_to(None))


def test_inline_query_builds_request_with_query_text_offset_and_limit() -> None:
    resolver = FakeResolveInlineQuery()
    dispatcher = make_handler(resolve_inline_query=resolver)
    bot = FakeBot()

    call_inline_get(dispatcher, bot, query="wave moon", offset="10")

    assert_that(
        resolver.calls[0],
        equal_to(InlineQueryRequest(user_id=123, query_text="wave moon", offset=10, limit=49)),
    )


@pytest.mark.parametrize(
    ("user_id", "expected_command"),
    [
        (789, ClearInlineCacheCommand(user_id=789)),
        (None, ClearInlineCacheCommand(user_id=None)),
    ],
)
def test_chosen_result_builds_cache_clear_command(
    user_id: int | None,
    expected_command: ClearInlineCacheCommand,
) -> None:
    clearer = FakeClearInlineCache()
    dispatcher = make_handler(clear_inline_cache=clearer)

    call_chosen_result(dispatcher, FakeBot(), user_id=user_id, query="wave moon")

    assert_that(clearer.calls, equal_to([expected_command]))


def test_chosen_result_does_not_send_query_text_across_application_boundary() -> None:
    clearer = FakeClearInlineCache()
    dispatcher = make_handler(clear_inline_cache=clearer)

    call_chosen_result(dispatcher, FakeBot(), query="wave moon")

    assert_that(clearer.calls[0], equal_to(ClearInlineCacheCommand(user_id=123)))
