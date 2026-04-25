from __future__ import annotations

import pytest
from hamcrest import assert_that, empty, equal_to, has_length, is_

from bot.application.errors import InvalidCommandInputError
from bot.application.requests import SetModeCommand
from bot.application.use_cases import SetMode
from bot.domain.user import StickfixUser


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, StickfixUser] = {}
        self.saved_users: list[StickfixUser] = []

    def get_user(self, user_id: str) -> StickfixUser | None:
        return self.users.get(user_id)

    def has_user(self, user_id: str) -> bool:
        return user_id in self.users

    def save_user(self, user: StickfixUser) -> None:
        self.users[str(user.id)] = user
        self.saved_users.append(user)

    def delete_user(self, user_id: str) -> bool:
        return self.users.pop(user_id, None) is not None

    def get_public_pack(self) -> StickfixUser | None:
        return self.get_user("SF-PUBLIC")

    def ensure_public_pack(self) -> StickfixUser:
        public_pack = self.get_public_pack()
        if public_pack is None:
            public_pack = StickfixUser("SF-PUBLIC")
            self.save_user(public_pack)
        return public_pack


def test_set_mode_creates_missing_user_in_private_mode() -> None:
    repository = FakeUserRepository()

    SetMode(repository)(SetModeCommand(user_id="alice", mode="private"))

    assert_that(repository.users["alice"].private_mode, is_(True))
    assert_that(repository.saved_users, equal_to([repository.users["alice"]]))


def test_set_mode_creates_missing_user_in_public_mode() -> None:
    repository = FakeUserRepository()

    SetMode(repository)(SetModeCommand(user_id="alice", mode="public"))

    assert_that(repository.users["alice"].private_mode, is_(False))
    assert_that(repository.saved_users, equal_to([repository.users["alice"]]))


def test_set_mode_updates_existing_user_to_private_mode() -> None:
    repository = FakeUserRepository()
    repository.users["alice"] = StickfixUser("alice")

    SetMode(repository)(SetModeCommand(user_id="alice", mode="private"))

    assert_that(repository.users["alice"].private_mode, is_(True))
    assert_that(repository.saved_users, equal_to([repository.users["alice"]]))


def test_set_mode_updates_existing_user_to_public_mode() -> None:
    repository = FakeUserRepository()
    repository.users["alice"] = StickfixUser("alice")
    repository.users["alice"].private_mode = True

    SetMode(repository)(SetModeCommand(user_id="alice", mode="public"))

    assert_that(repository.users["alice"].private_mode, is_(False))
    assert_that(repository.saved_users, equal_to([repository.users["alice"]]))


def test_set_mode_rejects_invalid_mode_without_saving() -> None:
    repository = FakeUserRepository()

    with pytest.raises(InvalidCommandInputError):
        SetMode(repository)(SetModeCommand(user_id="alice", mode="invalid"))

    assert_that(repository.users, equal_to({}))
    assert_that(repository.saved_users, empty())
