from __future__ import annotations

import pytest
from hamcrest import assert_that, equal_to, has_length, is_
from stickfix_domain import StickfixUser, UserId

from bot.application.errors import InvalidCommandInputError
from bot.application.requests import DeleteUserCommand, EnsureUserCommand, SetShuffleCommand
from bot.application.use_cases import DeleteUser, EnsureUser, SetShuffle
from tests.support.repositories import InMemoryUserRepository


def test_ensure_user_creates_unknown_numeric_user_once() -> None:
  users = InMemoryUserRepository()

  EnsureUser(users)(EnsureUserCommand(UserId(1)))
  EnsureUser(users)(EnsureUserCommand(UserId(1)))

  assert_that(users.users.keys(), equal_to({UserId(1)}))
  assert_that(users.saved_users, has_length(1))


def test_ensure_user_preserves_existing_user_state() -> None:
  users = InMemoryUserRepository()
  user = StickfixUser(UserId(1))
  user.private_mode = True
  user.shuffle = True
  users.save_user(user)
  users.saved_users.clear()

  EnsureUser(users)(EnsureUserCommand(UserId(1)))

  assert_that(users.get_user(UserId(1)), is_(user))
  assert_that(users.saved_users, equal_to([]))


@pytest.mark.parametrize(
  ("value", "expected"),
  [("on", True), ("off", False)],
)
def test_set_shuffle_persists_supported_values(value: str, expected: bool) -> None:
  users = InMemoryUserRepository()

  SetShuffle(users)(SetShuffleCommand(UserId(1), value))

  assert_that(users.get_user(UserId(1)).shuffle, is_(expected))


def test_set_shuffle_rejects_unsupported_value_without_mutation() -> None:
  users = InMemoryUserRepository()

  with pytest.raises(InvalidCommandInputError):
    SetShuffle(users)(SetShuffleCommand(UserId(1), "sometimes"))

  assert_that(users.users, equal_to({}))
  assert_that(users.saved_users, equal_to([]))


def test_delete_user_removes_existing_user_and_acknowledges() -> None:
  users = InMemoryUserRepository()
  users.save_user(StickfixUser(UserId(1)))

  result = DeleteUser(users)(DeleteUserCommand(UserId(1)))

  assert_that(result.acknowledged, is_(True))
  assert_that(users.users, equal_to({}))


def test_delete_user_missing_user_is_a_no_op() -> None:
  result = DeleteUser(InMemoryUserRepository())(DeleteUserCommand(UserId(1)))

  assert_that(result.acknowledged, is_(False))
