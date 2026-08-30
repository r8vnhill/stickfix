"""Shared repository helpers for the use-case layer.

Two concerns live here so individual use cases stay short and consistent:

* **Public-pack port bridging.** Production wiring passes a real
  :class:`~bot.application.ports.PublicPackRepository` (``PostgresUserRepository``
  implements it), but older tests still hand use cases a plain in-memory mapping or
  a fake with ad-hoc ``get_public_pack``/``ensure_public_pack`` methods.
  :func:`public_repository` normalises all of those into one ``PublicPackRepository``
  shape, and :func:`save_effective_pack` / :func:`get_user` paper over the same
  mapping-vs-repository split for reads and writes.
* **User resolution.** :func:`resolve_effective_user` is the single implementation of
  "load the addressed user, fall back to the public pack, otherwise raise" that the
  sticker and inline-query use cases all need.

Everything here is deliberately Telegram-free and imports only application ports,
application errors, and the domain model.
"""

from __future__ import annotations

from typing import cast

from bot.application.errors import UserNotFoundError
from bot.application.ports import PublicPackRepository, UserRepository
from bot.domain.user import StickfixUser

_NO_TARGET_MESSAGE = "No user or public sticker pack exists."


class _LegacyPublicPackRepository:
    """Bridge old in-memory fakes while production uses the dedicated port."""

    def __init__(self, users: object) -> None:
        self._users = users

    def get(self) -> StickfixUser | None:
        getter = getattr(self._users, "get_public_pack", None)
        if getter is not None:
            return cast(StickfixUser | None, getter())
        values = getattr(self._users, "values", None)
        if values is None:
            values = self._users.users.values()  # type: ignore[attr-defined]
        for value in values:
            if getattr(value, "id", None) == "SF-PUBLIC":
                return value
        return None

    def save(self, pack: StickfixUser) -> None:
        saver = getattr(self._users, "save_user", None)
        if saver is not None:
            saver(pack)
            return
        self._users[pack.id] = pack  # type: ignore[index]

    def ensure(self) -> StickfixUser:
        ensurer = getattr(self._users, "ensure_public_pack", None)
        if ensurer is not None:
            return cast(StickfixUser, ensurer())
        public = self.get()
        if public is not None:
            return public
        public = StickfixUser("SF-PUBLIC")
        self._users[public.id] = public  # type: ignore[index]
        return public


def public_repository(
    users: UserRepository,
    public: PublicPackRepository | None,
) -> PublicPackRepository:
    if public is not None:
        return public
    if isinstance(users, PublicPackRepository):
        return users
    return _LegacyPublicPackRepository(users)


def save_effective_pack(
    users: UserRepository,
    public: PublicPackRepository,
    pack: StickfixUser,
    public_pack: StickfixUser | None,
) -> None:
    if public_pack is not None and pack is public_pack:
        public.save(pack)
    else:
        saver = getattr(users, "save_user", None)
        if saver is not None:
            saver(pack)
        else:
            users[pack.id] = pack  # type: ignore[index]


def get_user(users: UserRepository, user_id: object) -> StickfixUser | None:
    getter = getattr(users, "get_user", None)
    if getter is not None:
        return cast(StickfixUser | None, getter(user_id))
    try:
        return cast(StickfixUser | None, users.get(user_id) or users.get(str(user_id)))  # type: ignore[attr-defined]
    except AttributeError:
        return None


def resolve_effective_user(
    users: UserRepository,
    user_id: object | None,
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
