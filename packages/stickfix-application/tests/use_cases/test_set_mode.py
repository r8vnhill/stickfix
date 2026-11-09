"""Mode changes persist through the user repository port.

These tests observe saved snapshots and fresh reads, not fake storage internals.
"""

from __future__ import annotations

import pytest
from hamcrest import assert_that, empty, equal_to, has_length, is_
from stickfix_application.errors import InvalidCommandInputError
from stickfix_application.requests import SetModeCommand
from stickfix_application.use_cases import SetMode
from stickfix_domain import StickfixUser, UserId
from support.repositories import InMemoryUserRepository


def test_set_mode_creates_missing_user_in_private_mode() -> None:
  repository = InMemoryUserRepository()

  SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="private"))

  assert_that(repository.get_user(UserId(1)).some.private_mode, is_(True))
  assert_that(repository.saved_users, has_length(1))
  assert_that(repository.saved_users[0].private_mode, is_(True))


def test_set_mode_creates_missing_user_in_public_mode() -> None:
  repository = InMemoryUserRepository()

  SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="public"))

  assert_that(repository.get_user(UserId(1)).some.private_mode, is_(False))
  assert_that(repository.saved_users, has_length(1))
  assert_that(repository.saved_users[0].private_mode, is_(False))


def test_set_mode_updates_existing_user_to_private_mode() -> None:
  repository = InMemoryUserRepository()
  repository.save_user(StickfixUser(UserId(1)))
  repository.saved_users.clear()

  SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="private"))

  assert_that(repository.get_user(UserId(1)).some.private_mode, is_(True))
  assert_that(repository.saved_users, has_length(1))
  assert_that(repository.saved_users[0].private_mode, is_(True))


def test_set_mode_updates_existing_user_to_public_mode() -> None:
  repository = InMemoryUserRepository()
  user = StickfixUser(UserId(1))
  user.private_mode = True
  repository.save_user(user)
  repository.saved_users.clear()

  SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="public"))

  assert_that(repository.get_user(UserId(1)).some.private_mode, is_(False))
  assert_that(repository.saved_users, has_length(1))
  assert_that(repository.saved_users[0].private_mode, is_(False))


def test_set_mode_rejects_invalid_mode_without_saving() -> None:
  repository = InMemoryUserRepository()

  with pytest.raises(InvalidCommandInputError):
    SetMode(repository)(SetModeCommand(user_id=UserId(1), mode="invalid"))

  assert_that(repository.has_user(UserId(1)), is_(False))
  assert_that(repository.saved_users, empty())
