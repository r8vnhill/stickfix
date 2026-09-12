"""Small in-memory implementations of the application repository ports."""

from __future__ import annotations

from stickfix_domain import StickfixUser, UserId


class InMemoryUserRepository:
  """Explicit regular-user repository fake for application tests."""

  def __init__(self) -> None:
    self.users: dict[UserId, StickfixUser] = {}
    self.saved_users: list[StickfixUser] = []

  def get_user(self, user_id: UserId) -> StickfixUser | None:
    return self.users.get(user_id)

  def has_user(self, user_id: UserId) -> bool:
    return user_id in self.users

  def save_user(self, user: StickfixUser) -> None:
    self.users[UserId(int(user.id))] = user
    self.saved_users.append(user)

  def delete_user(self, user_id: UserId) -> bool:
    return self.users.pop(user_id, None) is not None


class InMemoryPublicPackRepository:
  """Explicit shared-pack repository fake for application tests."""

  def __init__(self) -> None:
    self.pack: StickfixUser | None = None
    self.saved_packs: list[StickfixUser] = []

  def get(self) -> StickfixUser | None:
    return self.pack

  def save(self, pack: StickfixUser) -> None:
    self.pack = pack
    self.saved_packs.append(pack)

  def ensure(self) -> StickfixUser:
    if self.pack is None:
      self.pack = StickfixUser("public-pack")
    return self.pack
