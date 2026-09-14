"""PostgreSQL implementation of the application persistence ports.

``PostgresUserRepository`` implements both :class:`UserRepository` (regular numeric
users) and :class:`PublicPackRepository` (the shared pack). Every mutating method
runs inside ``session.begin()``, so once a call returns the change is already
committed -- there is no periodic flush and no in-memory write-behind.

Association storage is normalised into ``tags`` plus four ordered join tables
(user/public x sticker/cache). Reads and writes for all four go through the two
generic helpers :meth:`_load_associations` and :meth:`_save_associations`; the only
per-table detail is a small row-factory function (``_user_sticker_tag_row`` and
friends). Historical bulk import lives in the migration-only PostgreSQL gateway.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from functools import partial

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from stickfix_application.ports import PublicPackRepository, UserRepository
from stickfix_domain import SF_PUBLIC, StickfixUser, UserId

from .mappers import public_pack_from_rows, user_from_rows
from .models import (
  PublicCachedStickerRow,
  PublicStickerTagRow,
  StickerRow,
  TagRow,
  UserCachedStickerRow,
  UserRow,
  UserStickerTagRow,
)

# A row factory takes ``(tag_id, sticker_id, position)`` and returns a join-table row.
RowFactory = Callable[[int, str, int], object]


class PostgresUserRepository(UserRepository, PublicPackRepository):
  """Persist users and the public pack using one transaction per mutation."""

  def __init__(self, session_factory: Callable[[], Session]) -> None:
    self._session_factory = session_factory

  # -- UserRepository reads ------------------------------------------------

  def get_user(self, user_id: UserId) -> StickfixUser | None:
    with self._session_factory() as session:
      row = session.get(UserRow, int(user_id))
      if row is None:
        return None
      return user_from_rows(
        row,
        self._load_associations(session, UserStickerTagRow, user_id=int(user_id)),
        self._load_associations(session, UserCachedStickerRow, user_id=int(user_id)),
      )

  def has_user(self, user_id: UserId) -> bool:
    with self._session_factory() as session:
      return session.get(UserRow, int(user_id)) is not None

  # -- UserRepository writes ---------------------------------------------

  def save_user(self, user: StickfixUser) -> None:
    user_id = _require_user_id(user.id)
    with self._session_factory() as session, session.begin():
      row = session.get(UserRow, user_id)
      if row is None:
        row = UserRow(telegram_id=user_id)
        session.add(row)
      row.private_mode = bool(user.private_mode)
      row.shuffle = bool(user.shuffle)
      self._replace_user_rows(session, user_id, user)

  def delete_user(self, user_id: UserId) -> bool:
    with self._session_factory() as session, session.begin():
      row = session.get(UserRow, int(user_id))
      if row is None:
        return False
      session.delete(row)
      return True

  # -- PublicPackRepository --------------------------------------------

  def get(self) -> StickfixUser | None:
    with self._session_factory() as session:
      stickers = self._load_associations(session, PublicStickerTagRow)
      cache = self._load_associations(session, PublicCachedStickerRow)
      if not stickers and not cache:
        return None
      return public_pack_from_rows(stickers, cache)

  def save(self, pack: StickfixUser) -> None:
    with self._session_factory() as session, session.begin():
      session.execute(delete(PublicStickerTagRow))
      session.execute(delete(PublicCachedStickerRow))
      self._write_public_pack(session, pack)

  def ensure(self) -> StickfixUser:
    return self.get() or StickfixUser(SF_PUBLIC)

  # -- shared write helpers -------------------------------------------

  def _replace_user_rows(self, session: Session, user_id: int, user: StickfixUser) -> None:
    session.execute(delete(UserStickerTagRow).where(UserStickerTagRow.user_id == user_id))
    session.execute(delete(UserCachedStickerRow).where(UserCachedStickerRow.user_id == user_id))
    self._save_associations(session, user.stickers, partial(_user_sticker_tag_row, user_id))
    self._save_associations(
      session, user.cached_stickers, partial(_user_cached_sticker_row, user_id)
    )

  def _write_public_pack(self, session: Session, pack: StickfixUser) -> None:
    self._save_associations(session, pack.stickers, _public_sticker_tag_row)
    self._save_associations(session, pack.cached_stickers, _public_cached_sticker_row)

  def _save_associations(
    self,
    session: Session,
    associations: Mapping[str, list[str]],
    make_row: RowFactory,
  ) -> None:
    """Insert ordered ``(tag, sticker, position)`` rows built by ``make_row``.

    Tags and stickers referenced by the associations are created first so the
    join-table inserts never hit a missing foreign key.
    """
    tags = self._ensure_tags(session, set(associations))
    for sticker_id in {sid for values in associations.values() for sid in values}:
      self._ensure_sticker(session, sticker_id)
    session.flush()
    for tag, sticker_ids in associations.items():
      for position, sticker_id in enumerate(sticker_ids):
        session.add(make_row(tags[tag], sticker_id, position))

  @staticmethod
  def _ensure_sticker(session: Session, sticker_id: str) -> None:
    if not isinstance(sticker_id, str) or not sticker_id:
      raise ValueError("sticker ids must be non-empty strings")
    if session.get(StickerRow, sticker_id) is None:
      session.add(StickerRow(id=sticker_id))

  @staticmethod
  def _ensure_tags(session: Session, names: Iterable[str]) -> dict[str, int]:
    names = set(names)
    if not names:
      return {}
    rows = session.scalars(select(TagRow).where(TagRow.name.in_(names))).all()
    result = {row.name: row.id for row in rows}
    for name in names - result.keys():
      row = TagRow(name=name)
      session.add(row)
      session.flush()
      result[name] = row.id
    return result

  # -- shared read helper --------------------------------------------

  @staticmethod
  def _load_associations(
    session: Session,
    model: type,
    *,
    user_id: int | None = None,
  ) -> list:
    """Return ``(association_row, tag_name)`` pairs ordered by ``(tag_id, position)``."""
    stmt = (
      select(model, TagRow.name)
      .join(TagRow, TagRow.id == model.tag_id)
      .order_by(model.tag_id, model.position)
    )
    if user_id is not None:
      stmt = stmt.where(model.user_id == user_id)
    return session.execute(stmt).all()


def _user_sticker_tag_row(
  user_id: int, tag_id: int, sticker_id: str, position: int
) -> UserStickerTagRow:
  return UserStickerTagRow(
    user_id=user_id,
    tag_id=tag_id,
    sticker_id=sticker_id,
    position=position,
  )


def _user_cached_sticker_row(
  user_id: int, tag_id: int, sticker_id: str, position: int
) -> UserCachedStickerRow:
  return UserCachedStickerRow(
    user_id=user_id, tag_id=tag_id, sticker_id=sticker_id, position=position
  )


def _public_sticker_tag_row(tag_id: int, sticker_id: str, position: int) -> PublicStickerTagRow:
  return PublicStickerTagRow(tag_id=tag_id, sticker_id=sticker_id, position=position)


def _public_cached_sticker_row(
  tag_id: int, sticker_id: str, position: int
) -> PublicCachedStickerRow:
  return PublicCachedStickerRow(tag_id=tag_id, sticker_id=sticker_id, position=position)


def _require_user_id(value: object) -> int:
  if isinstance(value, bool) or not isinstance(value, int):
    raise TypeError("regular Stickfix users require an integer Telegram id")
  return value
