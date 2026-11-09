"""Test-only implementations of the application repository ports.

Use explicit saves in tests to model persistence boundaries. Reads and save-history
entries are detached snapshots; public state with no associations is represented
as absent, matching the PostgreSQL adapter without importing infrastructure code.
"""

from __future__ import annotations

from copy import deepcopy

from expression import Nothing, Option, Some
from stickfix_domain import SF_PUBLIC, StickfixUser, UserId


class InMemoryUserRepository:
  """Regular-user fake with detached reads, writes, and save observations."""

  def __init__(self) -> None:
    self._users: dict[UserId, StickfixUser] = {}
    self.saved_users: list[StickfixUser] = []

  def get_user(self, user_id: UserId) -> Option[StickfixUser]:
    user = self._users.get(user_id)
    return Some(deepcopy(user)) if user is not None else Nothing

  def has_user(self, user_id: UserId) -> bool:
    return user_id in self._users

  def save_user(self, user: StickfixUser) -> None:
    user_id = _require_user_id(user.id)
    snapshot = deepcopy(user)
    self._users[UserId(user_id)] = snapshot
    self.saved_users.append(deepcopy(snapshot))

  def delete_user(self, user_id: UserId) -> bool:
    return self._users.pop(user_id, None) is not None


class InMemoryPublicPackRepository:
  """Public-pack fake that persists only explicitly saved associations."""

  def __init__(self) -> None:
    self._stickers: dict[str, list[str]] = {}
    self._cached_stickers: dict[str, list[str]] = {}
    self.saved_packs: list[StickfixUser] = []

  def get(self) -> Option[StickfixUser]:
    if not self._stickers and not self._cached_stickers:
      return Nothing
    pack = StickfixUser(SF_PUBLIC)
    pack.stickers = deepcopy(self._stickers)
    pack.cached_stickers = deepcopy(self._cached_stickers)
    return Some(pack)

  def save(self, pack: StickfixUser) -> None:
    snapshot = deepcopy(pack)
    self._stickers = deepcopy(snapshot.stickers)
    self._cached_stickers = deepcopy(snapshot.cached_stickers)
    self.saved_packs.append(snapshot)

  def ensure(self) -> StickfixUser:
    return self.get().default_with(lambda: StickfixUser(SF_PUBLIC))


def _require_user_id(value: object) -> int:
  if isinstance(value, bool) or not isinstance(value, int):
    raise TypeError("regular Stickfix users require an integer Telegram id")
  return value
