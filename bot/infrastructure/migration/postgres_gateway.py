"""PostgreSQL gateway used only by the historical migration command.

The runtime repositories intentionally do not expose bulk import or full-database
projection operations. This gateway owns those migration concerns, imports only
into an empty database in one transaction, and projects rows back into the same
logical snapshot format used for source/target verification.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.infrastructure.persistence.postgres.models import (
  Base,
  PublicCachedStickerRow,
  PublicStickerTagRow,
  StickerRow,
  TagRow,
  UserCachedStickerRow,
  UserRow,
  UserStickerTagRow,
)

from .legacy_yaml import AssociationValues, LegacyUserRecord
from .logical_snapshot import (
  LogicalPersistenceSnapshot,
  snapshot_from_records,
)


class PostgresMigrationGateway:
  """Import and project migration snapshots without expanding runtime ports.

  ``session_factory`` is injected by the composition layer or migration CLI;
  callers are responsible for selecting the intended PostgreSQL database.
  """

  def __init__(self, session_factory: Callable[[], Session]) -> None:
    self._session_factory = session_factory

  def is_empty(self) -> bool:
    """Return whether all tables participating in migration are empty."""
    with self._session_factory() as session:
      return all(session.scalar(select(model).limit(1)) is None for model in _TABLES)

  def import_snapshot(self, snapshot: LogicalPersistenceSnapshot) -> None:
    """Import a validated snapshot atomically into an empty database.

    The emptiness check and all inserts share one transaction. Any constraint
    failure rolls back the complete import, leaving the target retryable.
    """
    with self._session_factory() as session, session.begin():
      self._require_empty(session)
      tags = self._ensure_tags(session, _all_tags(snapshot))
      self._ensure_stickers(session, _all_stickers(snapshot))
      self._write_users(session, snapshot, tags)
      self._write_public_associations(session, snapshot, tags)

  def read_snapshot(self) -> LogicalPersistenceSnapshot:
    """Read the complete PostgreSQL state as a canonical migration snapshot."""
    with self._session_factory() as session:
      users = tuple(
        self._user_record(session, row)
        for row in session.scalars(select(UserRow).order_by(UserRow.telegram_id))
      )
      public = self._public_record(session)
      return snapshot_from_records(users, public)

  @staticmethod
  def _require_empty(session: Session) -> None:
    if any(session.scalar(select(model).limit(1)) is not None for model in _TABLES):
      raise ValueError("target database must be empty before import")

  @staticmethod
  def _ensure_tags(session: Session, names: set[str]) -> dict[str, int]:
    rows = session.scalars(select(TagRow).where(TagRow.name.in_(names))).all()
    tags = {row.name: row.id for row in rows}
    for name in names - tags.keys():
      row = TagRow(name=name)
      session.add(row)
      session.flush()
      tags[name] = row.id
    return tags

  @staticmethod
  def _ensure_stickers(session: Session, names: set[str]) -> None:
    for name in names:
      if session.get(StickerRow, name) is None:
        session.add(StickerRow(id=name))
    session.flush()

  @staticmethod
  def _write_users(
    session: Session,
    snapshot: LogicalPersistenceSnapshot,
    tags: dict[str, int],
  ) -> None:
    for user in snapshot.users:
      session.add(
        UserRow(
          telegram_id=user.telegram_id,
          private_mode=user.private_mode,
          shuffle=user.shuffle,
        )
      )
    session.flush()
    for user in snapshot.users:
      PostgresMigrationGateway._write_associations(
        session, user.telegram_id, user.stickers, user.cached_stickers, tags
      )

  @staticmethod
  def _write_associations(
    session: Session,
    user_id: int,
    stickers: tuple,
    cached_stickers: tuple,
    tags: dict[str, int],
  ) -> None:
    _add_associations(session, stickers, tags, UserStickerTagRow, user_id)
    _add_associations(session, cached_stickers, tags, UserCachedStickerRow, user_id)

  @staticmethod
  def _write_public_associations(
    session: Session,
    snapshot: LogicalPersistenceSnapshot,
    tags: dict[str, int],
  ) -> None:
    _add_associations(session, snapshot.public_pack.stickers, tags, PublicStickerTagRow)
    _add_associations(session, snapshot.public_pack.cached_stickers, tags, PublicCachedStickerRow)

  @staticmethod
  def _user_record(session: Session, row: UserRow) -> LegacyUserRecord:
    return LegacyUserRecord(
      identifier=row.telegram_id,
      private_mode=row.private_mode,
      shuffle=row.shuffle,
      stickers=_read_associations(session, UserStickerTagRow, row.telegram_id),
      cached_stickers=_read_associations(session, UserCachedStickerRow, row.telegram_id),
    )

  @staticmethod
  def _public_record(session: Session) -> LegacyUserRecord | None:
    stickers = _read_associations(session, PublicStickerTagRow)
    cached_stickers = _read_associations(session, PublicCachedStickerRow)
    if not stickers and not cached_stickers:
      return None
    return LegacyUserRecord("SF-PUBLIC", False, False, stickers, cached_stickers)


_TABLES: tuple[type[Base], ...] = (
  UserRow,
  StickerRow,
  TagRow,
  UserStickerTagRow,
  PublicStickerTagRow,
  UserCachedStickerRow,
  PublicCachedStickerRow,
)


def _read_associations(
  session: Session,
  model: type,
  user_id: int | None = None,
) -> AssociationValues:
  statement = (
    select(model, TagRow.name)
    .join(TagRow, TagRow.id == model.tag_id)
    .order_by(TagRow.name, model.position)
  )
  if user_id is not None:
    statement = statement.where(model.user_id == user_id)
  grouped: dict[str, list[str]] = {}
  for row, tag in session.execute(statement):
    grouped.setdefault(tag, []).append(row.sticker_id)
  return tuple((tag, tuple(sticker_ids)) for tag, sticker_ids in grouped.items())


def _add_associations(
  session: Session,
  associations: tuple,
  tags: dict[str, int],
  model: type,
  user_id: int | None = None,
) -> None:
  for association in associations:
    values: dict[str, Any] = {
      "tag_id": tags[association.tag],
      "sticker_id": association.sticker_id,
      "position": association.position,
    }
    if user_id is not None:
      values["user_id"] = user_id
    session.add(model(**values))


def _all_tags(snapshot: LogicalPersistenceSnapshot) -> set[str]:
  return {association.tag for association in _all_associations(snapshot)}


def _all_stickers(snapshot: LogicalPersistenceSnapshot) -> set[str]:
  return {association.sticker_id for association in _all_associations(snapshot)}


def _all_associations(snapshot: LogicalPersistenceSnapshot) -> tuple:
  associations = []
  for user in snapshot.users:
    associations.extend(user.stickers)
    associations.extend(user.cached_stickers)
  associations.extend(snapshot.public_pack.stickers)
  associations.extend(snapshot.public_pack.cached_stickers)
  return tuple(associations)
