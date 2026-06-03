from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

import pytest
from hamcrest import (
    assert_that,
    empty,
    equal_to,
    has_length,
    instance_of,  # type: ignore[reportUnknownVariableType]
    is_,  # type: ignore[reportUnknownVariableType]
)
from telegram import InlineQueryResultArticle, InlineQueryResultCachedSticker, ParseMode
from telegram.ext import ChosenInlineResultHandler, InlineQueryHandler

from bot.application.requests import ClearInlineCacheCommand, InlineQueryRequest
from bot.application.results import AcknowledgementResult, InlineQueryResult
from bot.application.use_cases.clear_inline_cache import ClearInlineCache
from bot.application.use_cases.resolve_inline_query import ResolveInlineQuery
from bot.domain.user import SF_PUBLIC, StickfixUser
from bot.handlers.inline import InlineHandler


class FakeDispatcher:
    def __init__(self) -> None:
        self.handlers = []

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)


class FakeUserStore:
    def __init__(self) -> None:
        self.users: dict[object, StickfixUser] = {}
        self.writes: list[tuple[object, StickfixUser]] = []

    def __contains__(self, key: object) -> bool:
        return key in self.users

    def __getitem__(self, key: object) -> StickfixUser:
        return self.users[key]

    def __setitem__(self, key: object, value: StickfixUser) -> None:
        self.users[key] = value
        self.writes.append((key, value))

    def __delitem__(self, key: object) -> None:
        del self.users[key]

    def get(self, key: object) -> StickfixUser | None:
        """Get a user or return None if not found."""
        return self.users.get(key)


class FakeBot:
    def __init__(self) -> None:
        self.answer_inline_query_calls: list[dict[str, object]] = []

    def answer_inline_query(self, *args: object, **kwargs: object) -> None:
        self.answer_inline_query_calls.append({"args": args, "kwargs": kwargs})


class FakeResolveInlineQuery:
    """Fake use case that returns application layer results."""

    def __init__(self) -> None:
        self.calls: list[InlineQueryRequest] = []

    def __call__(self, request: InlineQueryRequest) -> InlineQueryResult:
        self.calls.append(request)
        return InlineQueryResult(
            sticker_ids=(),
            default_tags=(),
            show_default_help=False,
            help_text=None,
            next_offset=0,
        )


class FakeClearInlineCache:
    """Fake use case for clearing cache."""

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
    effective_user: FakeTelegramUser
    inline_query: FakeInlineQuery | None = None
    chosen_inline_result: FakeChosenInlineResult | None = None


def make_handler(
    store: FakeUserStore,
    resolve_inline_query: ResolveInlineQuery | None = None,
    clear_inline_cache: ClearInlineCache | None = None,
) -> InlineHandler:
    return InlineHandler(
        FakeDispatcher(),
        store,
        resolve_inline_query=resolve_inline_query,
        clear_inline_cache=clear_inline_cache,
    )


def inline_query_handler(dispatcher: FakeDispatcher) -> InlineQueryHandler:
    return next(
        handler for handler in dispatcher.handlers if isinstance(handler, InlineQueryHandler)
    )


def chosen_result_handler(dispatcher: FakeDispatcher) -> ChosenInlineResultHandler:
    return next(
        handler for handler in dispatcher.handlers if isinstance(handler, ChosenInlineResultHandler)
    )


def inline_query_callback(dispatcher: FakeDispatcher) -> Callable[..., object]:
    return inline_query_handler(dispatcher).callback


def chosen_result_callback(dispatcher: FakeDispatcher) -> Callable[..., object]:
    return chosen_result_handler(dispatcher).callback


def make_public_pack(store: FakeUserStore) -> StickfixUser:
    public_pack = StickfixUser(SF_PUBLIC)
    store[SF_PUBLIC] = public_pack
    store.writes.clear()
    return public_pack


def make_user(store: FakeUserStore, user_id: int, *, private_mode: bool = False) -> StickfixUser:
    user = StickfixUser(str(user_id))
    user.private_mode = private_mode
    store[str(user_id)] = user
    store.writes.clear()
    return user


def add_numbered_stickers(user: StickfixUser, tag: str, count: int) -> tuple[str, ...]:
    sticker_ids = tuple(f"sticker-{index:03d}" for index in range(count))
    for sticker_id in sticker_ids:
        user.add_sticker(sticker_id, [tag])
    return sticker_ids


def test_inline_handler_registers_inline_query_and_chosen_result_handlers() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    dispatcher = FakeDispatcher()

    InlineHandler(dispatcher, store)

    assert_that(dispatcher.handlers, has_length(2))
    assert_that(inline_query_handler(dispatcher), instance_of(InlineQueryHandler))
    assert_that(chosen_result_handler(dispatcher), instance_of(ChosenInlineResultHandler))
    assert_that(callable(inline_query_callback(dispatcher)), is_(True))
    assert_that(callable(chosen_result_callback(dispatcher)), is_(True))


def call_inline_get(
    handler: InlineHandler,
    bot: FakeBot,
    *,
    user_id: int = 123,
    query: str = "wave",
    offset: str = "0",
    inline_query_id: str = "inline-1",
) -> None:
    update = FakeUpdate(
        effective_user=FakeTelegramUser(user_id),
        inline_query=FakeInlineQuery(id=inline_query_id, query=query, offset=offset),
    )
    handler._InlineHandler__inline_get(update, FakeContext(bot=bot))


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


def test_empty_inline_query_at_first_page_includes_help_article_before_stickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(random, "choice", lambda tags: "wave")
    store = FakeUserStore()
    public_pack = make_public_pack(store)
    public_pack.add_sticker("empty-query-sticker", [""])
    public_pack.add_sticker("default-tag-sticker", ["wave"])
    bot = FakeBot()

    call_inline_get(make_handler(store), bot, query="")

    results = returned_results(bot)
    assert_that(results[0], instance_of(InlineQueryResultArticle))
    assert_that(results[0].title, equal_to("Click me for help"))
    assert_that(results[0].description, equal_to("Try calling me inline like `@stickfixbot wave`"))
    assert_that(results[0].input_message_content.parse_mode, equal_to(ParseMode.MARKDOWN))
    assert_that(results[1], instance_of(InlineQueryResultCachedSticker))
    assert_that(results[1].sticker_file_id, equal_to("empty-query-sticker"))
    assert_answer_arguments(bot)


def test_non_empty_inline_query_returns_cached_sticker_results_without_help_article() -> None:
    store = FakeUserStore()
    public_pack = make_public_pack(store)
    expected_stickers = add_numbered_stickers(public_pack, "wave", 2)
    bot = FakeBot()

    call_inline_get(make_handler(store), bot, query="wave")

    results = returned_results(bot)
    assert_that(results, has_length(2))
    assert_that(
        all(isinstance(result, InlineQueryResultCachedSticker) for result in results), is_(True)
    )
    assert_that(set(result.sticker_file_id for result in results), equal_to(set(expected_stickers)))
    assert_answer_arguments(bot)


def test_inline_query_first_page_returns_49_cached_stickers_with_set_materialized_order() -> None:
    store = FakeUserStore()
    public_pack = make_public_pack(store)
    expected_stickers = add_numbered_stickers(public_pack, "wave", 60)
    bot = FakeBot()

    call_inline_get(make_handler(store), bot, query="wave", offset="0")

    results = returned_results(bot)
    assert_that(results, has_length(49))
    returned_stickers = tuple(result.sticker_file_id for result in results)
    assert_that(set(returned_stickers).issubset(set(expected_stickers)), is_(True))
    assert_that(set(returned_stickers), has_length(49))
    assert_answer_arguments(bot, next_offset="49")


def test_inline_query_second_page_applies_offset_to_set_materialized_sticker_list() -> None:
    store = FakeUserStore()
    public_pack = make_public_pack(store)
    expected_stickers = add_numbered_stickers(public_pack, "wave", 100)
    bot = FakeBot()

    call_inline_get(make_handler(store), bot, query="wave", offset="49")

    results = returned_results(bot)
    assert_that(results, has_length(49))
    returned_stickers = tuple(result.sticker_file_id for result in results)
    assert_that(set(returned_stickers).issubset(set(expected_stickers)), is_(True))
    assert_that(set(returned_stickers), has_length(49))
    assert_answer_arguments(bot, next_offset="98")


@pytest.mark.parametrize(
    ("user_exists", "private_mode", "expected_sticker_id"),
    [
        (True, True, ("private-sticker",)),
        (True, False, ("private-sticker", "public-sticker")),
        (False, False, ("public-sticker",)),
    ],
)
def test_inline_query_resolves_current_public_private_fallback_behaviour(
    user_exists: bool,
    private_mode: bool,
    expected_sticker_id: tuple[str, ...],
) -> None:
    store = FakeUserStore()
    public_pack = make_public_pack(store)
    public_pack.add_sticker("public-sticker", ["wave"])
    if user_exists:
        user = make_user(store, 123, private_mode=private_mode)
        user.add_sticker("private-sticker", ["wave"])
    bot = FakeBot()

    call_inline_get(make_handler(store), bot, user_id=123, query="wave")

    results = returned_results(bot)
    assert_that(
        set(result.sticker_file_id for result in results), equal_to(set(expected_sticker_id))
    )


def test_chosen_result_clears_existing_user_cache_and_writes_user_back() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    user = make_user(store, 123, private_mode=True)
    user.cache["wave"] = ["cached-sticker"]
    bot = FakeBot()
    update = FakeUpdate(
        effective_user=FakeTelegramUser(123),
        chosen_inline_result=FakeChosenInlineResult(query="wave"),
    )

    make_handler(store)._InlineHandler__on_result(update, FakeContext(bot=bot))

    assert_that(user.cache, equal_to({}))
    assert_that(store.writes, equal_to([("123", user)]))


def test_chosen_result_for_missing_user_clears_public_pack_cache_and_writes_public_pack_back() -> (
    None
):
    store = FakeUserStore()
    public_pack = make_public_pack(store)
    public_pack.cache["wave"] = ["cached-sticker"]
    bot = FakeBot()
    update = FakeUpdate(
        effective_user=FakeTelegramUser(123),
        chosen_inline_result=FakeChosenInlineResult(query="wave"),
    )

    make_handler(store)._InlineHandler__on_result(update, FakeContext(bot=bot))

    assert_that(public_pack.cache, equal_to({}))
    assert_that(store.writes, equal_to([(SF_PUBLIC, public_pack)]))


def test_invalid_inline_query_offset_raises_value_error_and_does_not_answer_or_write() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    bot = FakeBot()

    with pytest.raises(ValueError):
        call_inline_get(make_handler(store), bot, query="wave", offset="not-an-int")

    assert_that(bot.answer_inline_query_calls, empty())
    assert_that(store.writes, empty())


# Tests for request/command mapping with fake use cases


def test_inline_query_builds_request_with_user_id_when_effective_user_exists() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    fake_use_case = FakeResolveInlineQuery()
    bot = FakeBot()

    call_inline_get(
        make_handler(store, resolve_inline_query=fake_use_case), bot, user_id=456, query="search"
    )

    assert_that(fake_use_case.calls, has_length(1))
    assert_that(fake_use_case.calls[0].user_id, equal_to("456"))


def test_inline_query_builds_request_with_none_user_id_when_effective_user_is_none() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    fake_use_case = FakeResolveInlineQuery()
    bot = FakeBot()
    update = FakeUpdate(
        effective_user=None,
        inline_query=FakeInlineQuery(id="inline-1", query="search", offset="0"),
    )

    handler = make_handler(store, resolve_inline_query=fake_use_case)
    handler._InlineHandler__inline_get(update, FakeContext(bot=bot))

    assert_that(fake_use_case.calls, has_length(1))
    assert_that(fake_use_case.calls[0].user_id, equal_to(None))


def test_inline_query_builds_request_with_query_text_and_offset() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    fake_use_case = FakeResolveInlineQuery()
    bot = FakeBot()

    call_inline_get(
        make_handler(store, resolve_inline_query=fake_use_case), bot, query="wave moon", offset="10"
    )

    request = fake_use_case.calls[0]
    assert_that(request.query_text, equal_to("wave moon"))
    assert_that(request.offset, equal_to(10))
    assert_that(request.limit, equal_to(49))


def test_inline_query_builds_help_article_from_application_result() -> None:
    store = FakeUserStore()
    make_public_pack(store)

    class CustomResolveInlineQuery:
        def __call__(self, request: InlineQueryRequest) -> InlineQueryResult:
            return InlineQueryResult(
                sticker_ids=(),
                default_tags=("wave", "hello"),
                show_default_help=True,
                help_text="This is help content",
                next_offset=0,
            )

    bot = FakeBot()
    call_inline_get(make_handler(store, resolve_inline_query=CustomResolveInlineQuery()), bot)

    results = returned_results(bot)
    assert_that(results[0], instance_of(InlineQueryResultArticle))
    assert_that(results[0].title, equal_to("Click me for help"))
    assert_that(results[0].description, equal_to("Try calling me inline like `@stickfixbot wave`"))
    assert_that(results[0].input_message_content.message_text, equal_to("This is help content"))


def test_chosen_result_builds_command_with_user_id_when_effective_user_exists() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    fake_use_case = FakeClearInlineCache()
    bot = FakeBot()
    update = FakeUpdate(
        effective_user=FakeTelegramUser(789),
        chosen_inline_result=FakeChosenInlineResult(query="test"),
    )

    make_handler(store, clear_inline_cache=fake_use_case)._InlineHandler__on_result(
        update, FakeContext(bot=bot)
    )

    assert_that(fake_use_case.calls, has_length(1))
    assert_that(fake_use_case.calls[0].user_id, equal_to("789"))


def test_chosen_result_builds_command_with_none_user_id_when_effective_user_is_none() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    fake_use_case = FakeClearInlineCache()
    bot = FakeBot()
    update = FakeUpdate(
        effective_user=None,
        chosen_inline_result=FakeChosenInlineResult(query="test"),
    )

    make_handler(store, clear_inline_cache=fake_use_case)._InlineHandler__on_result(
        update, FakeContext(bot=bot)
    )

    assert_that(fake_use_case.calls, has_length(1))
    assert_that(fake_use_case.calls[0].user_id, equal_to(None))


def test_chosen_result_builds_command_with_query_text() -> None:
    store = FakeUserStore()
    make_public_pack(store)
    fake_use_case = FakeClearInlineCache()
    bot = FakeBot()
    update = FakeUpdate(
        effective_user=FakeTelegramUser(123),
        chosen_inline_result=FakeChosenInlineResult(query="wave moon"),
    )

    make_handler(store, clear_inline_cache=fake_use_case)._InlineHandler__on_result(
        update, FakeContext(bot=bot)
    )

    assert_that(fake_use_case.calls[0].query_text, equal_to("wave moon"))
