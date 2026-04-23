"""Seam-level tests for the initial application package."""

from __future__ import annotations

import sys
from dataclasses import is_dataclass

from bot.application import errors, requests, results
from bot.application.ports import UserRepository
from bot.database.storage import StickfixDB
from bot.domain import SF_PUBLIC, StickfixUser


def test_application_modules_import_without_loading_telegram() -> None:
    assert "telegram" not in sys.modules
    assert "telegram.ext" not in sys.modules


def test_request_and_result_types_are_dataclasses() -> None:
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

    assert all(is_dataclass(dto_type) for dto_type in request_types + result_types)


def test_application_error_hierarchy_is_shallow_and_explicit() -> None:
    assert issubclass(errors.InvalidCommandInputError, errors.ApplicationError)
    assert issubclass(errors.WrongInteractionContextError, errors.ApplicationError)
    assert issubclass(errors.MissingStickerError, errors.ApplicationError)
    assert issubclass(errors.MissingReplyStickerError, errors.ApplicationError)
    assert issubclass(errors.UserNotFoundError, errors.ApplicationError)


def test_repository_port_can_be_targeted_by_a_small_adapter_for_stickfixdb(tmp_path) -> None:
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

    assert isinstance(adapter, UserRepository)
    assert adapter.get_user("missing") is None
    assert not adapter.has_user("missing")
    assert adapter.get_public_pack() is None
    assert adapter.ensure_public_pack().id == SF_PUBLIC
