"""Persistence-aware, test-only implementations of the application repository ports.

Every read returns a detached aggregate, and explicit repository operations update stored state.
Association lists with no sticker IDs do not produce stored associations. Save histories observe
calls, not database rows; these fakes never import the production adapter.
"""

from __future__ import annotations

from copy import deepcopy

from expression import Nothing, Option, Some
from stickfix_domain import SF_PUBLIC, StickfixUser, UserId


class InMemoryUserRepository:
  """Store detached snapshots for regular-user repository tests.

  Attributes:
    saved_users: Independent snapshots of successful save calls.
  """

  def __init__(self) -> None:
    """Initialize empty persisted-user and save-history collections."""
    self._users: dict[UserId, StickfixUser] = {}
    self.saved_users: list[StickfixUser] = []

  def get_user(self, user_id: UserId) -> Option[StickfixUser]:
    """Return a detached user snapshot when the ID is stored.

    Args:
      user_id: Numeric identifier of the regular user.

    Returns:
      `Some` with a detached user, or `Nothing` when the user is absent.
    """
    user = self._users.get(user_id)
    return Some(deepcopy(user)) if user is not None else Nothing

  def has_user(self, user_id: UserId) -> bool:
    """Check whether a regular user is stored.

    Args:
      user_id: Numeric identifier of the regular user.

    Returns:
      `True` if the ID has stored state; otherwise, `False`.
    """
    return user_id in self._users

  def save_user(self, user: StickfixUser) -> None:
    """Persist database-backed fields and record a detached save observation.

    Args:
      user: Aggregate to snapshot. Only its ID, preferences, and associations persist.

    Raises:
      TypeError: If the user ID is not an integer other than `bool`.
      ValueError: If an association contains invalid or repeated sticker IDs.
    """
    user_id = _require_user_id(user.id)
    snapshot = _regular_user_snapshot(user, user_id)
    self._users[UserId(user_id)] = snapshot
    self.saved_users.append(deepcopy(snapshot))

  def delete_user(self, user_id: UserId) -> bool:
    """Remove stored state for one regular user.

    Args:
      user_id: Numeric identifier of the regular user.

    Returns:
      `True` if a user was removed; otherwise, `False`.
    """
    return self._users.pop(user_id, None) is not None


class InMemoryPublicPackRepository:
  """Store public sticker associations without persisting empty packs.

  Attributes:
    saved_packs: Independent copies from successful `save()` calls.
  """

  def __init__(self) -> None:
    """Initialize empty sticker and cache association state."""
    self._stickers: dict[str, list[str]] = {}
    self._cached_stickers: dict[str, list[str]] = {}
    self.saved_packs: list[StickfixUser] = []

  def get(self) -> Option[StickfixUser]:
    """Reconstruct the canonical public pack when associations are stored.

    Returns:
      `Some` with a detached `SF_PUBLIC` pack, or `Nothing` when both
      association collections are empty.
    """
    if not self._stickers and not self._cached_stickers:
      return Nothing
    pack = StickfixUser(SF_PUBLIC)
    pack.stickers = deepcopy(self._stickers)
    pack.cached_stickers = deepcopy(self._cached_stickers)
    return Some(pack)

  def save(self, pack: StickfixUser) -> None:
    """Replace stored associations and record the submitted aggregate.

    Args:
      pack: Public-pack aggregate whose nonempty associations will be stored.

    Raises:
      ValueError: If an association contains invalid or repeated sticker IDs.
    """
    observation = deepcopy(pack)
    stickers = _persisted_associations(observation.stickers)
    cached_stickers = _persisted_associations(observation.cached_stickers)
    self._stickers = stickers
    self._cached_stickers = cached_stickers
    self.saved_packs.append(observation)

  def ensure(self) -> StickfixUser:
    """Return the stored pack or a new unsaved canonical empty pack.

    Returns:
      A detached stored pack, or a new `SF_PUBLIC` pack that is not persisted.
    """
    return self.get().default_with(lambda: StickfixUser(SF_PUBLIC))


def _regular_user_snapshot(user: StickfixUser, user_id: int) -> StickfixUser:
  """Rebuild only fields represented by the PostgreSQL user tables.

  Args:
    user: Source aggregate to project into stored fields.
    user_id: Validated numeric identifier for the stored user.

  Returns:
    A new aggregate containing the ID, boolean preferences, and associations.
  """
  snapshot = StickfixUser(UserId(user_id))
  snapshot.private_mode = bool(user.private_mode)
  snapshot.shuffle = bool(user.shuffle)
  snapshot.stickers = _persisted_associations(user.stickers)
  snapshot.cached_stickers = _persisted_associations(user.cached_stickers)
  return snapshot


def _persisted_associations(associations: dict[str, list[str]]) -> dict[str, list[str]]:
  """Copy nonempty tag lists that can be represented by association rows.

  Args:
    associations: Tag-to-sticker-ID mapping from an aggregate.

  Returns:
    A detached mapping without empty lists, preserving order within each tag.

  Raises:
    ValueError: If a list contains an empty, non-string, or repeated sticker ID.
  """
  stored: dict[str, list[str]] = {}
  for tag, sticker_ids in associations.items():
    if not sticker_ids:
      continue
    if any(not isinstance(sticker_id, str) or not sticker_id for sticker_id in sticker_ids):
      raise ValueError("sticker ids must be non-empty strings")
    if len(sticker_ids) != len(set(sticker_ids)):
      raise ValueError("duplicate sticker ids for one tag are not supported")
    stored[tag] = list(sticker_ids)
  return stored


def _require_user_id(value: object) -> int:
  """Validate and return the numeric ID required by regular-user storage.

  Args:
    value: Candidate aggregate identifier.

  Returns:
    The integer user ID.

  Raises:
    TypeError: If the value is not an integer or is a boolean.
  """
  if isinstance(value, bool) or not isinstance(value, int):
    raise TypeError("regular Stickfix users require an integer Telegram id")
  return value
