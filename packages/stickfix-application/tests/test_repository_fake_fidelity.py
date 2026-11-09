"""Additional behavioral checks for persistence-aware in-memory repositories."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from expression import Nothing
from stickfix_domain import SF_PUBLIC, StickfixUser, UserId
from support.repositories import InMemoryPublicPackRepository, InMemoryUserRepository

InvalidSaveCase = tuple[
  Callable[[], None],
  Callable[[], dict[str, list[str]]],
  Callable[[], int],
]


@pytest.mark.parametrize("owner", ["regular", "public"])
def test_empty_tag_lists_create_no_persisted_associations(owner: str) -> None:
  """Given empty tag lists, when saved, no association rows are represented."""
  user = StickfixUser(UserId(1) if owner == "regular" else SF_PUBLIC)
  user.stickers = {"unused": []}
  user.cached_stickers = {"unused-cache": []}

  if owner == "regular":
    repository = InMemoryUserRepository()
    repository.save_user(user)
    loaded = repository.get_user(UserId(1)).some
    assert loaded.stickers == {}
    assert loaded.cached_stickers == {}
  else:
    public = InMemoryPublicPackRepository()
    public.save(user)
    assert public.get() is Nothing
    assert len(public.saved_packs) == 1


@pytest.mark.parametrize("owner", ["regular", "public"])
def test_empty_tag_lists_are_removed_when_other_associations_exist(owner: str) -> None:
  """Given mixed tag lists, when saved and reloaded, only nonempty tags remain."""
  user = StickfixUser(UserId(1) if owner == "regular" else SF_PUBLIC)
  user.stickers = {"empty": [], "wave": ["s1", "s2"]}
  user.cached_stickers = {"unused": [], "wave": ["s2"]}

  if owner == "regular":
    repository = InMemoryUserRepository()
    repository.save_user(user)
    loaded = repository.get_user(UserId(1)).some
  else:
    public = InMemoryPublicPackRepository()
    public.save(user)
    loaded = public.get().some

  assert loaded.stickers == {"wave": ["s1", "s2"]}
  assert loaded.cached_stickers == {"wave": ["s2"]}
  assert user.stickers["empty"] == []


def test_regular_user_read_excludes_non_persisted_attributes() -> None:
  """Given application-only attributes, when saved and reloaded, they are absent."""
  repository = InMemoryUserRepository()
  user = StickfixUser(UserId(1))
  user.temporary_note = "not part of the persistence contract"
  repository.save_user(user)

  assert not hasattr(repository.get_user(UserId(1)).some, "temporary_note")
  assert not hasattr(repository.saved_users[0], "temporary_note")


def test_regular_user_preferences_follow_database_boolean_conversion() -> None:
  """Given truthy preference values, when saved, subsequent reads yield booleans."""
  repository = InMemoryUserRepository()
  user = StickfixUser(UserId(1))
  user.private_mode = 1
  user.shuffle = 1
  repository.save_user(user)

  loaded = repository.get_user(UserId(1)).some
  assert loaded.private_mode is True
  assert loaded.shuffle is True


@pytest.mark.parametrize("owner", ["regular", "public"])
@pytest.mark.parametrize("identifier", [None, "", 123])
def test_invalid_sticker_identifiers_retain_previous_saved_state(
  owner: str, identifier: object
) -> None:
  """Given existing associations, an unsupported save leaves storage and history unchanged."""
  save, read_stickers, save_count = _invalid_save_case(owner, identifier)
  with pytest.raises(ValueError, match="non-empty strings"):
    save()
  assert read_stickers() == {"wave": ["saved"]}
  assert save_count() == 1


def _invalid_save_case(
  owner: str,
  identifier: object,
) -> InvalidSaveCase:
  if owner == "regular":
    return _regular_invalid_save_case(identifier)
  return _public_invalid_save_case(identifier)


def _regular_invalid_save_case(
  identifier: object,
) -> InvalidSaveCase:
  repository = InMemoryUserRepository()
  existing = StickfixUser(UserId(1))
  existing.stickers = {"wave": ["saved"]}
  repository.save_user(existing)
  candidate = repository.get_user(UserId(1)).some
  candidate.stickers["wave"] = [identifier]
  return (
    lambda: repository.save_user(candidate),
    lambda: repository.get_user(UserId(1)).some.stickers,
    lambda: len(repository.saved_users),
  )


def _public_invalid_save_case(
  identifier: object,
) -> InvalidSaveCase:
  public = InMemoryPublicPackRepository()
  existing = StickfixUser(SF_PUBLIC)
  existing.stickers = {"wave": ["saved"]}
  public.save(existing)
  candidate = public.get().some
  candidate.stickers["wave"] = [identifier]
  return (
    lambda: public.save(candidate),
    lambda: public.get().some.stickers,
    lambda: len(public.saved_packs),
  )


@pytest.mark.parametrize("owner", ["regular", "public"])
def test_duplicate_associations_do_not_partially_update_repository(owner: str) -> None:
  """Given duplicate values under one tag, save rejection retains earlier state."""
  user = StickfixUser(UserId(1) if owner == "regular" else SF_PUBLIC)
  user.stickers = {"wave": ["saved"]}

  if owner == "regular":
    repository = InMemoryUserRepository()
    repository.save_user(user)
    candidate = repository.get_user(UserId(1)).some
    candidate.stickers["wave"] = ["s1", "s1"]
    with pytest.raises(ValueError, match="duplicate"):
      repository.save_user(candidate)
    assert repository.get_user(UserId(1)).some.stickers == {"wave": ["saved"]}
    assert len(repository.saved_users) == 1
  else:
    public = InMemoryPublicPackRepository()
    public.save(user)
    candidate = public.get().some
    candidate.stickers["wave"] = ["s1", "s1"]
    with pytest.raises(ValueError, match="duplicate"):
      public.save(candidate)
    assert public.get().some.stickers == {"wave": ["saved"]}
    assert len(public.saved_packs) == 1


def test_public_observation_records_input_but_reads_reconstruct_canonical_pack() -> None:
  """Given a supplied pack identifier, stored reads use the public sentinel."""
  public = InMemoryPublicPackRepository()
  pack = StickfixUser("caller-supplied-label")
  pack.stickers = {"wave": ["s1"]}
  public.save(pack)
  pack.stickers["wave"].append("unsaved")

  assert public.get().some.id == SF_PUBLIC
  assert public.get().some.stickers == {"wave": ["s1"]}
  assert public.saved_packs[0].id == "caller-supplied-label"
  assert public.saved_packs[0].stickers == {"wave": ["s1"]}
