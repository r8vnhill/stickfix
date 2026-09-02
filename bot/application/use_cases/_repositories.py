"""Repository helpers shared by the pack-oriented use cases.

The use cases operate on an "effective pack" that is either the caller's own
record or the shared ``SF-PUBLIC`` pack. These helpers centralise the two places
that distinction matters -- persisting a mutated pack back to the right port, and
resolving which pack a request targets -- so each use case stays a few lines long
and they cannot drift apart. Everything here is Telegram-free and depends only on
application ports, application errors, and the domain model.
"""

from __future__ import annotations

from bot.application.errors import UserNotFoundError
from bot.application.ports import PublicPackRepository, UserRepository
from bot.domain.identifiers import UserId
from bot.domain.user import StickfixUser

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


def get_user(users: UserRepository, user_id: UserId) -> StickfixUser | None:
    """Load one regular numeric user through the explicit user port."""
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
    user = get_user(users, user_id) if user_id is not None else None
    if user is not None:
        return user
    if public_pack is None:
        raise UserNotFoundError(_NO_TARGET_MESSAGE)
    return public_pack
