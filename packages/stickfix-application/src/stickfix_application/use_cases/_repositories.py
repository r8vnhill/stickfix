"""Repository helpers shared by the pack-oriented use cases.

The use cases operate on an "effective pack" that is either the caller's own
record or the shared ``SF-PUBLIC`` pack. These helpers centralise the two places
that distinction matters -- persisting a mutated pack back to the right port, and
resolving which pack a request targets -- so each use case stays a few lines long
and they cannot drift apart. Repository absence stays an Expression `Option` until
this module applies a use-case fallback or raises the established domain-facing
error. This module remains Telegram-free and depends on application ports, errors,
and the domain model.
"""

from __future__ import annotations

from expression import Nothing, Option
from stickfix_domain import StickfixUser, UserId

from ..errors import UserNotFoundError
from ..ports import PublicPackRepository, UserRepository

_NO_TARGET_MESSAGE = "No user or public sticker pack exists."


def save_effective_pack(
  users: UserRepository,
  public: PublicPackRepository,
  pack: StickfixUser,
  public_pack: StickfixUser | None,
) -> None:
  """Persist ``pack`` through the port that owns it.

  Identity (``is``) against ``public_pack`` -- not id equality -- decides the
  target, so a use case that loaded the public pack as its fallback writes back
  to the public port while a real user's pack goes to the user port.
  """
  if public_pack is not None and pack is public_pack:
    public.save(pack)
  else:
    users.save_user(pack)


def get_user(users: UserRepository, user_id: UserId) -> Option[StickfixUser]:
  """Load a regular user while preserving the port's explicit absence value."""
  return users.get_user(user_id)


def resolve_effective_user(
  users: UserRepository,
  user_id: UserId | None,
  public_pack: StickfixUser | None,
) -> StickfixUser:
  """Return the addressed user, else the public pack, else raise.

  Args:
      users: Repository (or legacy fake) to load the regular user from.
      user_id: Numeric Telegram id of the caller, or ``None`` for anonymous
          inline traffic.
      public_pack: The shared pack when it exists, used as the fallback target.

  Raises:
      UserNotFoundError: Neither a matching user nor a public pack is available.
  """
  user = get_user(users, user_id) if user_id is not None else Nothing
  return user.default_with(lambda: _public_pack_or_raise(public_pack))


def _public_pack_or_raise(public_pack: StickfixUser | None) -> StickfixUser:
  if public_pack is None:
    raise UserNotFoundError(_NO_TARGET_MESSAGE)
  return public_pack
