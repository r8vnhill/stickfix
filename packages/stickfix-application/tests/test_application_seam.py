"""Seam-level tests for the explicit application contracts."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import fields, is_dataclass

import stickfix_application
from hamcrest import assert_that, equal_to, is_
from stickfix_application import ports, requests, results, use_cases
from stickfix_application.ports import PublicPackRepository, UserRepository
from support.repositories import InMemoryPublicPackRepository, InMemoryUserRepository

_FORBIDDEN_TOP_LEVEL_MODULES = ("telegram", "sqlalchemy", "psycopg", "alembic", "bot")
_EXPECTED_PACKAGE_EXPORTS = [
  "AcknowledgementResult",
  "AddStickerCommand",
  "ApplicationError",
  "ClearInlineCache",
  "ClearInlineCacheCommand",
  "DeleteStickerCommand",
  "DeleteUserCommand",
  "GetStickersQuery",
  "GetHelp",
  "InteractionScope",
  "GetStickersResult",
  "InlineQueryRequest",
  "InlineQueryResult",
  "InvalidCommandInputError",
  "MissingReplyStickerError",
  "MissingStickerError",
  "SetModeCommand",
  "SetShuffleCommand",
  "UserNotFoundError",
  "WrongInteractionContextError",
]


def test_application_package_imports_without_infrastructure_in_a_fresh_interpreter() -> None:
  """A clean interpreter importing the application package loads no infrastructure."""
  script = (
    "import sys\n"
    "import stickfix_application\n"
    "import stickfix_application.errors\n"
    "import stickfix_application.requests\n"
    "import stickfix_application.results\n"
    "import stickfix_application.ports\n"
    "import stickfix_application.use_cases\n"
    f"forbidden = {_FORBIDDEN_TOP_LEVEL_MODULES!r}\n"
    "loaded = sorted(name for name in forbidden if name in sys.modules)\n"
    "print(','.join(loaded))\n"
  )
  # The command uses the current interpreter and a literal script.
  result = subprocess.run(  # noqa: S603
    [sys.executable, "-c", script],
    capture_output=True,
    text=True,
    check=True,
  )

  assert_that(result.stdout.strip(), equal_to(""))


def test_package_public_surface_is_unchanged() -> None:
  """The package facade keeps the extraction's deliberately narrow API."""
  assert_that(stickfix_application.__all__, equal_to(_EXPECTED_PACKAGE_EXPORTS))


def test_ports_public_surface_is_unchanged() -> None:
  assert_that(
    ports.__all__,
    equal_to(["HelpContentProvider", "PublicPackRepository", "UserRepository"]),
  )


def test_use_cases_public_surface_is_unchanged() -> None:
  assert_that(
    use_cases.__all__,
    equal_to(
      [
        "AddSticker",
        "ClearInlineCache",
        "DeleteUser",
        "DeleteSticker",
        "EnsureUser",
        "GetStickers",
        "GetHelp",
        "ResolveInlineQuery",
        "SetMode",
        "SetShuffle",
      ]
    ),
  )


def test_request_and_result_types_are_dataclasses() -> None:
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
