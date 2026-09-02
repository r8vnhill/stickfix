from __future__ import annotations

import pytest
from hamcrest import assert_that, empty, equal_to, has_length, is_

from bot.application.errors import InvalidCommandInputError
from bot.application.requests import SetModeCommand
from bot.application.use_cases import SetMode
from bot.domain.identifiers import UserId
from bot.domain.user import StickfixUser
from tests.support.repositories import InMemoryUserRepository


def test_set_mode_creates_missing_user_in_private_mode() -> None:
    repository = InMemoryUserRepository()

    SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="private"))

    assert_that(repository.users[UserId(1)].private_mode, is_(True))
    assert_that(repository.saved_users, equal_to([repository.users[UserId(1)]]))


def test_set_mode_creates_missing_user_in_public_mode() -> None:
    repository = InMemoryUserRepository()

    SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="public"))

    assert_that(repository.users[UserId(1)].private_mode, is_(False))
    assert_that(repository.saved_users, equal_to([repository.users[UserId(1)]]))


def test_set_mode_updates_existing_user_to_private_mode() -> None:
    repository = InMemoryUserRepository()
    repository.users[UserId(1)] = StickfixUser(UserId(1))

    SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="private"))

    assert_that(repository.users[UserId(1)].private_mode, is_(True))
    assert_that(repository.saved_users, equal_to([repository.users[UserId(1)]]))


def test_set_mode_updates_existing_user_to_public_mode() -> None:
    repository = InMemoryUserRepository()
    repository.users[UserId(1)] = StickfixUser(UserId(1))
    repository.users[UserId(1)].private_mode = True

    SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="public"))

    assert_that(repository.users[UserId(1)].private_mode, is_(False))
    assert_that(repository.saved_users, equal_to([repository.users[UserId(1)]]))


def test_set_mode_rejects_invalid_mode_without_saving() -> None:
    repository = InMemoryUserRepository()

    with pytest.raises(InvalidCommandInputError):
        SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="invalid"))

    assert_that(repository.users, equal_to({}))
    assert_that(repository.saved_users, empty())
