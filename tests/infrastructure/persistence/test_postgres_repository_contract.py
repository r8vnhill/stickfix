"""PostgreSQL adapter contracts, including behavior shared with application fakes.

The opt-in fixture truncates the database configured by
``STICKFIX_TEST_DATABASE_URL`` before and after each test. Use only a disposable
database; keep these integration checks outside application-package tests.
"""

# The repository's test suite uses plain assertions for readable contract checks.
# ruff: noqa: S101

from __future__ import annotations

import os

import pytest
from expression import Nothing
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from stickfix_domain import SF_PUBLIC, StickfixUser, UserId

from bot.infrastructure.migration.legacy_yaml import LegacyStoreRecord, LegacyUserRecord
from bot.infrastructure.migration.logical_snapshot import snapshot_from_legacy
from bot.infrastructure.migration.postgres_gateway import PostgresMigrationGateway
from bot.infrastructure.persistence.postgres import (
  PostgresUserRepository,
  create_engine_and_session_factory,
)

DATABASE_URL = os.environ.get("STICKFIX_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture
def postgres_repository():
  if not DATABASE_URL:
    pytest.skip("set STICKFIX_TEST_DATABASE_URL to run PostgreSQL contract tests")
  engine, factory = create_engine_and_session_factory(DATABASE_URL)
  with engine.begin() as connection:
    connection.execute(
      text(
        "TRUNCATE users, public_sticker_tags, public_cached_stickers, "
        "user_sticker_tags, user_cached_stickers, stickers, tags "
        "RESTART IDENTITY CASCADE"
      )
    )
  yield PostgresUserRepository(factory)
  with engine.begin() as connection:
    connection.execute(
      text(
        "TRUNCATE users, public_sticker_tags, public_cached_stickers, "
        "user_sticker_tags, user_cached_stickers, stickers, tags "
        "RESTART IDENTITY CASCADE"
      )
    )
  engine.dispose()


def test_user_and_public_pack_round_trip(postgres_repository) -> None:
  user = StickfixUser(UserId(123))
  user.private_mode = True
  user.shuffle = True
  user.stickers = {"wave": ["s1", "s2"]}
  user.cached_stickers = {"wave": ["s2", "s3"]}
  public = StickfixUser("SF-PUBLIC")
  public.stickers = {"public": ["s4"]}
  public.cached_stickers = {"public": ["s5"]}

  postgres_repository.save_user(user)
  postgres_repository.save(public)

  loaded_user = postgres_repository.get_user(UserId(123)).some
  loaded_public = postgres_repository.get().some
  assert loaded_user.private_mode is True
  assert loaded_user.shuffle is True
  assert loaded_user.stickers == user.stickers
  assert loaded_user.cached_stickers == user.cached_stickers
  assert loaded_public.stickers == public.stickers
  assert loaded_public.cached_stickers == public.cached_stickers


def test_failed_user_mutation_rolls_back(postgres_repository) -> None:
  user = StickfixUser(UserId(123))
  user.stickers = {"wave": ["s1"]}
  postgres_repository.save_user(user)

  invalid = StickfixUser(UserId(123))
  invalid.stickers = {"wave": [None]}  # type: ignore[list-item]
  with pytest.raises((TypeError, ValueError, IntegrityError)):
    postgres_repository.save_user(invalid)

  loaded = postgres_repository.get_user(UserId(123)).some
  assert loaded.stickers == {"wave": ["s1"]}


def test_public_ensure_and_empty_saves_are_not_retrievable(postgres_repository) -> None:
  assert postgres_repository.get() is Nothing
  transient_pack = postgres_repository.ensure()
  assert transient_pack.id == SF_PUBLIC
  assert postgres_repository.get() is Nothing
  postgres_repository.save(transient_pack)
  assert postgres_repository.get() is Nothing


def test_empty_tag_lists_do_not_produce_retrievable_associations(postgres_repository) -> None:
  """Empty tag values produce no association rows even beside stored tags."""
  user = StickfixUser(UserId(123))
  user.stickers = {"unused": [], "wave": ["s1"]}
  user.cached_stickers = {"unused-cache": []}
  postgres_repository.save_user(user)

  regular = postgres_repository.get_user(UserId(123)).some
  assert regular.stickers == {"wave": ["s1"]}
  assert regular.cached_stickers == {}

  public = StickfixUser(SF_PUBLIC)
  public.stickers = {"unused": [], "wave": ["s2"]}
  public.cached_stickers = {"unused-cache": []}
  postgres_repository.save(public)

  loaded = postgres_repository.get().some
  assert loaded.stickers == {"wave": ["s2"]}
  assert loaded.cached_stickers == {}


def test_public_pack_reads_are_detached(postgres_repository) -> None:
  public = StickfixUser(SF_PUBLIC)
  public.stickers = {"wave": ["public-sticker"]}
  public.cached_stickers = {"wave": ["cached-public-sticker"]}
  postgres_repository.save(public)
  loaded = postgres_repository.get().some
  loaded.stickers["wave"].append("unsaved-public-sticker")
  loaded.cached_stickers["wave"].clear()

  unchanged = postgres_repository.get().some
  assert unchanged.stickers == {"wave": ["public-sticker"]}
  assert unchanged.cached_stickers == {"wave": ["cached-public-sticker"]}


def test_clearing_public_associations_removes_retrievable_state(postgres_repository) -> None:
  public = StickfixUser(SF_PUBLIC)
  public.stickers = {"wave": ["public-sticker"]}
  postgres_repository.save(public)
  loaded = postgres_repository.get().some
  loaded.stickers.clear()
  postgres_repository.save(loaded)

  assert postgres_repository.get() is Nothing


def _saved_contract_user(repository: PostgresUserRepository) -> None:
  user = StickfixUser(UserId(123))
  user.stickers = {"wave": ["s1"]}
  user.cached_stickers = {"wave": ["c1"]}
  repository.save_user(user)


def test_regular_user_reads_are_detached(postgres_repository) -> None:
  _saved_contract_user(postgres_repository)
  loaded = postgres_repository.get_user(UserId(123)).some
  loaded.stickers["wave"].append("unsaved")
  loaded.cached_stickers["wave"].clear()

  unchanged = postgres_repository.get_user(UserId(123)).some
  assert unchanged.stickers == {"wave": ["s1"]}
  assert unchanged.cached_stickers == {"wave": ["c1"]}


def test_regular_user_update_and_delete_contract(postgres_repository) -> None:
  _saved_contract_user(postgres_repository)
  user = postgres_repository.get_user(UserId(123)).some
  user.private_mode = True
  user.stickers["wave"].append("s2")
  postgres_repository.save_user(user)

  saved = postgres_repository.get_user(UserId(123)).some
  assert saved.private_mode is True
  assert saved.stickers == {"wave": ["s1", "s2"]}

  assert postgres_repository.delete_user(UserId(123)) is True
  assert postgres_repository.get_user(UserId(123)) is Nothing
  assert postgres_repository.has_user(UserId(123)) is False
  assert postgres_repository.delete_user(UserId(123)) is False


def test_runtime_repository_does_not_expose_migration_operations() -> None:
  assert not hasattr(PostgresUserRepository, "import_mapping")
  assert not hasattr(PostgresUserRepository, "iter_user_ids")
  assert not hasattr(PostgresUserRepository, "is_empty")


def test_migration_gateway_round_trips_a_logical_snapshot(postgres_repository) -> None:
  gateway = PostgresMigrationGateway(postgres_repository._session_factory)
  expected = snapshot_from_legacy(_migration_source())

  gateway.import_snapshot(expected)

  assert gateway.read_snapshot().as_dict() == expected.as_dict()


def _migration_source() -> LegacyStoreRecord:
  return LegacyStoreRecord(
    users=(
      LegacyUserRecord(
        identifier=123,
        private_mode=True,
        shuffle=True,
        stickers=(("wave", ("s1", "s2")),),
        cached_stickers=(("wave", ("s2",)),),
      ),
    ),
    public_pack=LegacyUserRecord(
      identifier="SF-PUBLIC",
      private_mode=False,
      shuffle=False,
      stickers=(("public", ("s3",)),),
      cached_stickers=(),
    ),
  )
