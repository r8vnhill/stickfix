"""Seam-level tests for the explicit application contracts."""

from __future__ import annotations

import importlib
import sys
from dataclasses import fields, is_dataclass

from hamcrest import assert_that, equal_to, has_item, is_, is_not

from bot.application.ports import PublicPackRepository, UserRepository
from tests.support.repositories import InMemoryPublicPackRepository, InMemoryUserRepository


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
    requests.EnsureUserCommand,
    requests.InlineQueryRequest,
    requests.ClearInlineCacheCommand,
  ]
  result_types = [
    results.AcknowledgementResult,
    results.AddStickerResult,
    results.DeleteStickerResult,
    results.GetStickersResult,
    results.InlineQueryResult,
  ]

  actual = [is_dataclass(dto_type) for dto_type in request_types + result_types]
  assert_that(actual, equal_to([True] * len(actual)))


def test_repository_ports_are_implemented_by_explicit_test_fakes() -> None:
  assert_that(isinstance(InMemoryUserRepository(), UserRepository), is_(True))
  assert_that(isinstance(InMemoryPublicPackRepository(), PublicPackRepository), is_(True))


def test_sticker_requests_contain_only_application_data() -> None:
  requests = importlib.import_module("bot.application.requests")

  assert_that(
    {field.name for field in fields(requests.AddStickerCommand)},
    equal_to({"user_id", "reply_sticker_id", "reply_sticker_emoji", "tags"}),
  )
  assert_that(
    {field.name for field in fields(requests.DeleteStickerCommand)},
    equal_to({"user_id", "reply_sticker_id", "tags"}),
  )
  assert_that(
    {field.name for field in fields(requests.ClearInlineCacheCommand)},
    equal_to({"user_id"}),
  )
