from __future__ import annotations

from hamcrest import assert_that, is_, none, same_instance

from bot.domain.user import StickfixUser
from bot.infrastructure.persistence import StickfixUserRepository


def test_repository_loads_existing_user_from_stickfixdb(store) -> None:
    user = StickfixUser("alice")
    store["alice"] = user
    repository = StickfixUserRepository(store)

    assert_that(repository.get_user("alice"), same_instance(user))
    assert_that(repository.has_user("alice"), is_(True))


def test_repository_represents_missing_user_as_none(store) -> None:
    repository = StickfixUserRepository(store)

    assert_that(repository.get_user("missing"), none())
    assert_that(repository.has_user("missing"), is_(False))


def test_repository_saves_mutations_to_underlying_store(store) -> None:
    repository = StickfixUserRepository(store)
    user = StickfixUser("alice")
    user.private_mode = True

    repository.save_user(user)

    assert_that(store["alice"].private_mode, is_(True))
