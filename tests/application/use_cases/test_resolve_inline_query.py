from __future__ import annotations

import random

import pytest
from hamcrest import assert_that, equal_to, has_length, is_, none

from bot.application.errors import UserNotFoundError
from bot.application.requests import InlineQueryRequest
from bot.application.use_cases import ResolveInlineQuery
from bot.domain.user import SF_PUBLIC, StickfixUser


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, StickfixUser] = {}
        self.saved_users: list[StickfixUser] = []

    def get_user(self, user_id: str) -> StickfixUser | None:
        return self.users.get(user_id)

    def has_user(self, user_id: str) -> bool:
        return user_id in self.users

    def save_user(self, user: StickfixUser) -> None:
        self.users[user.id] = user
        self.saved_users.append(user)

    def delete_user(self, user_id: str) -> bool:
        return self.users.pop(user_id, None) is not None

    def get_public_pack(self) -> StickfixUser | None:
        return self.get_user(SF_PUBLIC)

    def ensure_public_pack(self) -> StickfixUser:
        public_pack = self.get_public_pack()
        if public_pack is None:
            public_pack = StickfixUser(SF_PUBLIC)
            self.save_user(public_pack)
        return public_pack


class FakeHelpContentProvider:
    def __init__(self, help_text: str = "help text") -> None:
        self.help_text = help_text
        self.calls = 0

    def get_help_text(self) -> str:
        self.calls += 1
        return self.help_text


def make_use_case(
    repository: FakeUserRepository,
    help_provider: FakeHelpContentProvider | None = None,
) -> ResolveInlineQuery:
    return ResolveInlineQuery(repository, help_provider or FakeHelpContentProvider())


def add_numbered_stickers(user: StickfixUser, tag: str, count: int) -> tuple[str, ...]:
    sticker_ids = tuple(f"sticker-{index:03d}" for index in range(count))
    for sticker_id in sticker_ids:
        user.add_sticker(sticker_id, [tag])
    return sticker_ids


def test_missing_repository_user_falls_back_to_public_pack() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("public-sticker", ["wave"])
    repository.saved_users.clear()

    result = make_use_case(repository)(
        InlineQueryRequest(user_id="missing", query_text="wave"),
    )

    assert_that(result.sticker_ids, equal_to(("public-sticker",)))
    assert_that(repository.saved_users, equal_to([public_pack]))


def test_none_user_id_falls_back_to_public_pack() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("public-sticker", ["wave"])
    repository.saved_users.clear()

    result = make_use_case(repository)(
        InlineQueryRequest(user_id=None, query_text="wave"),
    )

    assert_that(result.sticker_ids, equal_to(("public-sticker",)))
    assert_that(repository.saved_users, equal_to([public_pack]))


def test_missing_user_without_public_pack_raises_user_not_found() -> None:
    repository = FakeUserRepository()

    with pytest.raises(UserNotFoundError):
        make_use_case(repository)(InlineQueryRequest(user_id="missing", query_text="wave"))


def test_public_mode_user_preserves_current_public_and_own_union_behaviour() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("public-sticker", ["wave"])
    user = StickfixUser("alice")
    user.add_sticker("private-sticker", ["wave"])
    repository.users[user.id] = user
    repository.saved_users.clear()

    result = make_use_case(repository)(
        InlineQueryRequest(user_id="alice", query_text="wave"),
    )

    assert_that(set(result.sticker_ids), equal_to({"private-sticker", "public-sticker"}))
    assert_that(repository.saved_users, equal_to([user]))


def test_private_mode_user_resolves_only_private_stickers() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("public-sticker", ["wave"])
    user = StickfixUser("alice")
    user.private_mode = True
    user.add_sticker("private-sticker", ["wave"])
    repository.users[user.id] = user
    repository.saved_users.clear()

    result = make_use_case(repository)(
        InlineQueryRequest(user_id="alice", query_text="wave"),
    )

    assert_that(result.sticker_ids, equal_to(("private-sticker",)))
    assert_that(repository.saved_users, equal_to([user]))


def test_empty_query_at_first_page_returns_help_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(random, "choice", lambda tags: "wave")
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("empty-query-sticker", [""])
    public_pack.add_sticker("default-tag-sticker", ["wave"])
    help_provider = FakeHelpContentProvider("raw help")
    repository.saved_users.clear()

    result = make_use_case(repository, help_provider)(
        InlineQueryRequest(user_id=None, query_text="", offset=0),
    )

    assert_that(result.show_default_help, is_(True))
    assert_that(result.help_text, equal_to("raw help"))
    assert_that(result.default_tags, equal_to(("wave",)))
    assert_that(result.sticker_ids, equal_to(("empty-query-sticker",)))
    assert_that(help_provider.calls, equal_to(1))
    assert_that(repository.saved_users, equal_to([public_pack]))


def test_empty_query_after_first_page_does_not_return_help_metadata() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("empty-query-sticker", [""])
    help_provider = FakeHelpContentProvider("raw help")
    repository.saved_users.clear()

    result = make_use_case(repository, help_provider)(
        InlineQueryRequest(user_id=None, query_text="", offset=49),
    )

    assert_that(result.show_default_help, is_(False))
    assert_that(result.help_text, none())
    assert_that(result.default_tags, equal_to(()))
    assert_that(help_provider.calls, equal_to(0))


def test_non_empty_query_does_not_read_help_content() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("public-sticker", ["wave"])
    help_provider = FakeHelpContentProvider("raw help")
    repository.saved_users.clear()

    result = make_use_case(repository, help_provider)(
        InlineQueryRequest(user_id=None, query_text="wave"),
    )

    assert_that(result.show_default_help, is_(False))
    assert_that(result.help_text, none())
    assert_that(help_provider.calls, equal_to(0))


def test_paginates_stickers_with_legacy_next_offset() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    expected_stickers = add_numbered_stickers(public_pack, "wave", 100)
    repository.saved_users.clear()

    result = make_use_case(repository)(
        InlineQueryRequest(user_id=None, query_text="wave", offset=49),
    )

    assert_that(result.sticker_ids, has_length(49))
    assert_that(set(result.sticker_ids).issubset(set(expected_stickers)), is_(True))
    assert_that(result.next_offset, equal_to(98))


def test_pagination_allows_fewer_than_limit_and_no_remaining_stickers() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    add_numbered_stickers(public_pack, "wave", 2)
    repository.saved_users.clear()

    partial_result = make_use_case(repository)(
        InlineQueryRequest(user_id=None, query_text="wave", offset=1),
    )
    empty_result = make_use_case(repository)(
        InlineQueryRequest(user_id=None, query_text="wave", offset=49),
    )

    assert_that(partial_result.sticker_ids, has_length(1))
    assert_that(partial_result.next_offset, equal_to(50))
    assert_that(empty_result.sticker_ids, equal_to(()))
    assert_that(empty_result.next_offset, equal_to(98))


def test_private_lookup_saves_user_after_cache_mutation() -> None:
    repository = FakeUserRepository()
    repository.ensure_public_pack()
    user = StickfixUser("alice")
    user.private_mode = True
    user.add_sticker("private-sticker", ["wave"])
    repository.users[user.id] = user
    repository.saved_users.clear()

    make_use_case(repository)(InlineQueryRequest(user_id="alice", query_text="wave"))

    assert_that(user.cache, equal_to({"wave": ["private-sticker"]}))
    assert_that(repository.saved_users, equal_to([user]))
