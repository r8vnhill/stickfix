from __future__ import annotations

import pytest
from hamcrest import assert_that, equal_to, is_

from bot.application.errors import UserNotFoundError
from bot.application.requests import ClearInlineCacheCommand
from bot.application.results import AcknowledgementResult
from bot.application.use_cases import ClearInlineCache
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


def make_use_case(repository: FakeUserRepository) -> ClearInlineCache:
    return ClearInlineCache(repository)


def add_cached_stickers(user: StickfixUser) -> None:
    user.cache["wave"] = ["cached-wave"]
    user.cache["smile"] = ["cached-smile"]


def test_clears_private_user_cache_when_existing_user_is_in_private_mode() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    user = StickfixUser("alice")
    user.private_mode = True
    add_cached_stickers(user)
    add_cached_stickers(public_pack)
    repository.users[user.id] = user
    repository.saved_users.clear()

    make_use_case(repository)(ClearInlineCacheCommand(user_id="alice"))

    assert_that(user.cache, equal_to({}))
    assert_that(public_pack.cache, equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}))
    assert_that(repository.saved_users, equal_to([user]))


def test_clears_public_cache_when_existing_user_is_in_public_mode() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    user = StickfixUser("alice")
    add_cached_stickers(user)
    add_cached_stickers(public_pack)
    repository.users[user.id] = user
    repository.saved_users.clear()

    make_use_case(repository)(ClearInlineCacheCommand(user_id="alice"))

    assert_that(public_pack.cache, equal_to({}))
    assert_that(user.cache, equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}))
    assert_that(repository.saved_users, equal_to([public_pack]))


def test_clears_public_cache_when_user_id_is_none() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    add_cached_stickers(public_pack)
    repository.saved_users.clear()

    make_use_case(repository)(ClearInlineCacheCommand(user_id=None))

    assert_that(public_pack.cache, equal_to({}))
    assert_that(repository.saved_users, equal_to([public_pack]))


def test_clears_public_cache_when_user_id_is_unknown() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    add_cached_stickers(public_pack)
    repository.saved_users.clear()

    make_use_case(repository)(ClearInlineCacheCommand(user_id="missing"))

    assert_that(public_pack.cache, equal_to({}))
    assert_that(repository.saved_users, equal_to([public_pack]))


def test_raises_when_public_cache_owner_is_missing() -> None:
    repository = FakeUserRepository()

    with pytest.raises(UserNotFoundError):
        make_use_case(repository)(ClearInlineCacheCommand(user_id="missing"))

    assert_that(repository.saved_users, equal_to([]))


def test_returns_acknowledgement_result() -> None:
    repository = FakeUserRepository()
    repository.ensure_public_pack()
    repository.saved_users.clear()

    result = make_use_case(repository)(ClearInlineCacheCommand(user_id=None))

    assert_that(result, equal_to(AcknowledgementResult(acknowledged=True)))


def test_ignores_query_text() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    add_cached_stickers(public_pack)
    repository.saved_users.clear()

    make_use_case(repository)(ClearInlineCacheCommand(user_id=None, query_text="wave"))

    assert_that(public_pack.cache, equal_to({}))
    assert_that(repository.saved_users, equal_to([public_pack]))


def test_saves_only_the_resolved_cache_owner_and_leaves_unrelated_users_untouched() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    user = StickfixUser("alice")
    unrelated = StickfixUser("bob")
    add_cached_stickers(public_pack)
    add_cached_stickers(user)
    add_cached_stickers(unrelated)
    repository.users[user.id] = user
    repository.users[unrelated.id] = unrelated
    repository.saved_users.clear()

    make_use_case(repository)(ClearInlineCacheCommand(user_id="alice"))

    assert_that(public_pack.cache, equal_to({}))
    assert_that(user.cache, equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}))
    assert_that(unrelated.cache, equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}))
    assert_that(repository.saved_users, equal_to([public_pack]))
    assert_that(repository.saved_users.count(public_pack), is_(1))
