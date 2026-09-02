from __future__ import annotations

import pytest
from hamcrest import assert_that, equal_to

from bot.application.errors import UserNotFoundError
from bot.application.requests import ClearInlineCacheCommand
from bot.application.results import AcknowledgementResult
from bot.application.use_cases import ClearInlineCache
from bot.domain.identifiers import UserId
from bot.domain.user import StickfixUser
from tests.support.repositories import InMemoryPublicPackRepository, InMemoryUserRepository


def make_repositories() -> tuple[InMemoryUserRepository, InMemoryPublicPackRepository]:
    users = InMemoryUserRepository()
    public = InMemoryPublicPackRepository()
    public_pack = public.ensure()
    public.save(public_pack)
    public.saved_packs.clear()
    return users, public


def add_cached_stickers(user: StickfixUser) -> None:
    user.cache["wave"] = ["cached-wave"]
    user.cache["smile"] = ["cached-smile"]


def test_clears_private_user_cache_when_existing_user_is_in_private_mode() -> None:
    users, public = make_repositories()
    add_cached_stickers(public.pack)
    user = StickfixUser(UserId(1))
    user.private_mode = True
    add_cached_stickers(user)
    users.save_user(user)
    users.saved_users.clear()

    ClearInlineCache(users, public)(ClearInlineCacheCommand(UserId(1)))

    assert_that(user.cache, equal_to({}))
    assert_that(public.pack.cache, equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}))
    assert_that(users.saved_users, equal_to([user]))


def test_clears_public_cache_when_existing_user_is_in_public_mode() -> None:
    users, public = make_repositories()
    add_cached_stickers(public.pack)
    user = StickfixUser(UserId(1))
    add_cached_stickers(user)
    users.save_user(user)
    users.saved_users.clear()

    ClearInlineCache(users, public)(ClearInlineCacheCommand(UserId(1)))

    assert_that(public.pack.cache, equal_to({}))
    assert_that(user.cache, equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}))
    assert_that(public.saved_packs, equal_to([public.pack]))


def test_clears_public_cache_when_user_id_is_none_or_unknown() -> None:
    for user_id in (None, UserId(2)):
        users, public = make_repositories()
        add_cached_stickers(public.pack)
        public.saved_packs.clear()

        ClearInlineCache(users, public)(ClearInlineCacheCommand(user_id))

        assert_that(public.pack.cache, equal_to({}))
        assert_that(public.saved_packs, equal_to([public.pack]))


def test_raises_when_public_cache_owner_is_missing() -> None:
    with pytest.raises(UserNotFoundError):
        ClearInlineCache(InMemoryUserRepository(), InMemoryPublicPackRepository())(
            ClearInlineCacheCommand(UserId(2))
        )


def test_returns_acknowledgement_result() -> None:
    users, public = make_repositories()

    result = ClearInlineCache(users, public)(ClearInlineCacheCommand(None))

    assert_that(result, equal_to(AcknowledgementResult(acknowledged=True)))


def test_saves_only_the_resolved_cache_owner_and_leaves_unrelated_users_untouched() -> None:
    users, public = make_repositories()
    user = StickfixUser(UserId(1))
    unrelated = StickfixUser(UserId(2))
    add_cached_stickers(public.pack)
    add_cached_stickers(user)
    add_cached_stickers(unrelated)
    users.save_user(user)
    users.save_user(unrelated)
    users.saved_users.clear()

    ClearInlineCache(users, public)(ClearInlineCacheCommand(UserId(1)))

    assert_that(public.pack.cache, equal_to({}))
    assert_that(
        user.cache,
        equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}),
    )
    assert_that(
        unrelated.cache,
        equal_to({"wave": ["cached-wave"], "smile": ["cached-smile"]}),
    )
    assert_that(public.saved_packs, equal_to([public.pack]))
