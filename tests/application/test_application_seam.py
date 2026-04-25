"""Seam-level tests for the initial application package."""

from __future__ import annotations

import importlib
import sys
from dataclasses import is_dataclass

from hamcrest import assert_that, equal_to, has_item, is_, is_not, none

from bot.database.storage import StickfixDB
from bot.domain import SF_PUBLIC, StickfixUser


def test_application_modules_import_without_loading_telegram() -> None:
    before = set(sys.modules)

    importlib.import_module("bot.application")
    importlib.import_module("bot.application.errors")
    importlib.import_module("bot.application.requests")
    importlib.import_module("bot.application.results")
    importlib.import_module("bot.application.ports")
    importlib.import_module("bot.application.use_cases")

    added = set(sys.modules) - before
    assert_that(added, is_not(has_item("telegram")))
    assert_that(added, is_not(has_item("telegram.ext")))


def test_request_and_result_types_are_dataclasses() -> None:
    requests = importlib.import_module("bot.application.requests")
    results = importlib.import_module("bot.application.results")
    request_types = [
        requests.AddStickerCommand,
        requests.GetStickersQuery,
        requests.DeleteStickerCommand,
        requests.SetModeCommand,
        requests.SetShuffleCommand,
        requests.DeleteUserCommand,
        requests.InlineQueryRequest,
        requests.ClearInlineCacheCommand,
    ]
    result_types = [
        results.AcknowledgementResult,
        results.GetStickersResult,
        results.InlineQueryResult,
    ]

    actual = [is_dataclass(dto_type) for dto_type in request_types + result_types]
    assert_that(actual, equal_to([True] * len(actual)))


def test_application_error_hierarchy_is_shallow_and_explicit() -> None:
    errors = importlib.import_module("bot.application.errors")
    assert_that(issubclass(errors.InvalidCommandInputError, errors.ApplicationError), is_(True))
    assert_that(issubclass(errors.WrongInteractionContextError, errors.ApplicationError), is_(True))
    assert_that(issubclass(errors.MissingStickerError, errors.ApplicationError), is_(True))
    assert_that(issubclass(errors.MissingReplyStickerError, errors.ApplicationError), is_(True))
    assert_that(issubclass(errors.UserNotFoundError, errors.ApplicationError), is_(True))


def test_repository_port_can_be_targeted_by_a_small_adapter_for_stickfixdb(tmp_path) -> None:
    ports = importlib.import_module("bot.application.ports")
    store = StickfixDB("users", data_dir=tmp_path)

    class StickfixDbRepositoryAdapter:
        def __init__(self, wrapped: StickfixDB) -> None:
            self._wrapped = wrapped

        def get_user(self, user_id: str) -> StickfixUser | None:
            return self._wrapped.get(user_id)

        def has_user(self, user_id: str) -> bool:
            return user_id in self._wrapped

        def save_user(self, user: StickfixUser) -> None:
            self._wrapped[str(user.id)] = user

        def delete_user(self, user_id: str) -> bool:
            if user_id not in self._wrapped:
                return False
            del self._wrapped[user_id]
            return True

        def get_public_pack(self) -> StickfixUser | None:
            return self._wrapped.get(SF_PUBLIC)

        def ensure_public_pack(self) -> StickfixUser:
            public_user = self.get_public_pack()
            if public_user is None:
                public_user = StickfixUser(SF_PUBLIC)
                self.save_user(public_user)
            return public_user

    adapter = StickfixDbRepositoryAdapter(store)

    assert_that(isinstance(adapter, ports.UserRepository), is_(True))
    assert_that(adapter.get_user("missing"), none())
    assert_that(adapter.has_user("missing"), is_(False))
    assert_that(adapter.get_public_pack(), none())
    assert_that(adapter.ensure_public_pack().id, is_(SF_PUBLIC))
