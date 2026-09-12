"""SQLAlchemy models for the normalized Stickfix persistence schema.

Schema map (see ``alembic/versions/0001_initial_postgres_schema.py`` for the DDL):

* ``users`` -- one row per regular Telegram user, holding only the preferences.
* ``stickers`` / ``tags`` -- de-duplicated value tables.
* ``user_sticker_tags`` / ``public_sticker_tags`` -- the owned pack contents, one
  row per ``(owner, sticker, tag)`` with an explicit ``position`` for ordering.
* ``user_cached_stickers`` / ``public_cached_stickers`` -- the inline-query result
  cache, same shape.

The public pack has no identity row: an empty pack is simply zero ``public_*`` rows.
``Mapped``/``mapped_column`` types stay in sync with ``Base.metadata`` so
``alembic check`` can detect drift.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Identity, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
  """Declarative base; ``Base.metadata`` is the Alembic ``target_metadata``."""


class UserRow(Base):
  """A regular user keyed by Telegram id; associations live in the join tables."""

  __tablename__ = "users"

  telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
  private_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  shuffle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class StickerRow(Base):
  __tablename__ = "stickers"

  id: Mapped[str] = mapped_column(String, primary_key=True)


class TagRow(Base):
  __tablename__ = "tags"

  id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
  name: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class UserStickerTagRow(Base):
  __tablename__ = "user_sticker_tags"
  __table_args__ = (Index("ix_user_sticker_tags_user_tag", "user_id", "tag_id"),)

  user_id: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("users.telegram_id", ondelete="CASCADE"),
    primary_key=True,
  )
  sticker_id: Mapped[str] = mapped_column(
    String,
    ForeignKey("stickers.id", ondelete="CASCADE"),
    primary_key=True,
  )
  tag_id: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("tags.id", ondelete="CASCADE"),
    primary_key=True,
  )
  position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PublicStickerTagRow(Base):
  __tablename__ = "public_sticker_tags"
  __table_args__ = (Index("ix_public_sticker_tags_tag", "tag_id"),)

  sticker_id: Mapped[str] = mapped_column(
    String,
    ForeignKey("stickers.id", ondelete="CASCADE"),
    primary_key=True,
  )
  tag_id: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("tags.id", ondelete="CASCADE"),
    primary_key=True,
  )
  position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class UserCachedStickerRow(Base):
  __tablename__ = "user_cached_stickers"
  __table_args__ = (Index("ix_user_cached_stickers_user_tag", "user_id", "tag_id"),)

  user_id: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("users.telegram_id", ondelete="CASCADE"),
    primary_key=True,
  )
  tag_id: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("tags.id", ondelete="CASCADE"),
    primary_key=True,
  )
  sticker_id: Mapped[str] = mapped_column(String, primary_key=True)
  position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PublicCachedStickerRow(Base):
  __tablename__ = "public_cached_stickers"
  __table_args__ = (Index("ix_public_cached_stickers_tag", "tag_id"),)

  tag_id: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("tags.id", ondelete="CASCADE"),
    primary_key=True,
  )
  sticker_id: Mapped[str] = mapped_column(String, primary_key=True)
  position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
