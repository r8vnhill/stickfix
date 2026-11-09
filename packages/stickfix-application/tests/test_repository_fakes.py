"""Behavioral contract tests for the application package's in-memory fakes.

Keep these checks at the port boundary: tests should observe explicit saves,
fresh reads, and save histories rather than the fakes' private storage layout.
"""

from __future__ import annotations

import pytest
from expression import Nothing
from hamcrest import assert_that, equal_to, is_
from stickfix_domain import SF_PUBLIC, StickfixUser, UserId
from support.repositories import InMemoryPublicPackRepository, InMemoryUserRepository


def _saved_user_repository() -> tuple[InMemoryUserRepository, StickfixUser]:
  repository = InMemoryUserRepository()
  user = StickfixUser(UserId(1))
  user.private_mode = True
  user.add_sticker("sticker-1", ["wave"])
  user.cache["wave"] = ["cached-1"]
  repository.save_user(user)
  return repository, user


def test_user_reads_are_detached_from_original_and_loaded_objects() -> None:
  repository, original = _saved_user_repository()
  original.private_mode = False
  original.stickers["wave"].append("unsaved-original")
  loaded = repository.get_user(UserId(1)).some
  loaded.private_mode = False
  loaded.stickers["wave"].append("unsaved-read")
  loaded.cache["wave"].append("unsaved-read-cache")

  unchanged = repository.get_user(UserId(1)).some
  assert_that(unchanged.private_mode, is_(True))
  assert_that(unchanged.stickers, equal_to({"wave": ["sticker-1"]}))
  assert_that(unchanged.cache, equal_to({"wave": ["cached-1"]}))


def test_user_save_updates_state_and_keeps_earlier_history() -> None:
  repository, original = _saved_user_repository()
  original.private_mode = False
  updated = repository.get_user(UserId(1)).some
  updated.private_mode = False
  updated.add_sticker("sticker-2", ["smile"])
  updated.cache["smile"] = ["cached-2"]
  repository.save_user(updated)

  saved = repository.get_user(UserId(1)).some
  assert_that(saved.private_mode, is_(False))
  assert_that(saved.stickers, equal_to({"wave": ["sticker-1"], "smile": ["sticker-2"]}))
  assert_that(saved.cache, equal_to({"wave": ["cached-1"], "smile": ["cached-2"]}))
  assert_that(repository.saved_users[0].private_mode, is_(True))
  assert_that(repository.saved_users[1].private_mode, is_(False))


@pytest.mark.parametrize("identifier", [UserId(123), 123])
def test_regular_user_accepts_and_round_trips_integer_identifiers(identifier: int) -> None:
  repository = InMemoryUserRepository()
  user = StickfixUser(identifier)

  repository.save_user(user)

  assert_that(repository.get_user(UserId(123)).is_some(), is_(True))
  assert_that(repository.get_user(UserId(123)).some.id, equal_to(UserId(123)))
  assert_that(repository.has_user(UserId(123)), is_(True))


@pytest.mark.parametrize("identifier", ["123", 123.9, True, None])
def test_invalid_regular_user_identifier_does_not_change_repository(identifier: object) -> None:
  repository = InMemoryUserRepository()
  initial = StickfixUser(UserId(456))
  repository.save_user(initial)
  repository.saved_users.clear()

  with pytest.raises(TypeError):
    repository.save_user(StickfixUser(identifier))

  assert_that(repository.get_user(UserId(456)).some.id, equal_to(UserId(456)))
  assert_that(repository.has_user(UserId(123)), is_(False))
  assert_that(repository.get_user(UserId(123)), is_(Nothing))
  assert_that(repository.saved_users, equal_to([]))


def test_user_deletion_updates_lookup_and_existence() -> None:
  repository = InMemoryUserRepository()
  repository.save_user(StickfixUser(UserId(1)))

  assert_that(repository.delete_user(UserId(1)), is_(True))
  assert_that(repository.get_user(UserId(1)), is_(Nothing))
  assert_that(repository.has_user(UserId(1)), is_(False))
  assert_that(repository.delete_user(UserId(1)), is_(False))


def test_public_ensure_is_canonical_and_does_not_persist() -> None:
  repository = InMemoryPublicPackRepository()

  pack = repository.ensure()

  assert_that(pack.id, equal_to(SF_PUBLIC))
  assert_that(repository.get(), is_(Nothing))


def test_public_pack_round_trip_is_detached_and_empty_state_is_absent() -> None:
  repository = InMemoryPublicPackRepository()
  pack = repository.ensure()
  pack.add_sticker("sticker-1", ["wave", "smile"])
  pack.cache["wave"] = ["cached-1"]
  repository.save(pack)
  pack.stickers["wave"].append("unsaved-original")

  assert_that(repository.get().is_some(), is_(True))
  loaded = repository.get().some
  loaded.stickers["wave"].append("unsaved-read")
  loaded.cache["wave"].clear()
  unchanged = repository.get().some
  assert_that(unchanged.id, equal_to(SF_PUBLIC))
  assert_that(unchanged.stickers, equal_to({"wave": ["sticker-1"], "smile": ["sticker-1"]}))
  assert_that(unchanged.cache, equal_to({"wave": ["cached-1"]}))
  assert_that(repository.saved_packs[0].cache, equal_to({"wave": ["cached-1"]}))

  unchanged.stickers.clear()
  unchanged.cache.clear()
  repository.save(unchanged)
  assert_that(repository.get(), is_(Nothing))
  assert_that(
    repository.saved_packs[0].stickers, equal_to({"wave": ["sticker-1"], "smile": ["sticker-1"]})
  )


def test_empty_public_save_does_not_create_retrievable_state() -> None:
  repository = InMemoryPublicPackRepository()

  repository.save(repository.ensure())

  assert_that(repository.get(), is_(Nothing))
  assert_that(repository.saved_packs[0].id, equal_to(SF_PUBLIC))
