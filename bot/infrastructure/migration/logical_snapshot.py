"""Backend-independent, deterministic migration snapshots.

Snapshots are the comparison contract between the legacy YAML projection and a
PostgreSQL migration gateway. Associations are sorted by tag, position, and
sticker id, then serialized with stable JSON options so a SHA-256 digest can be
recorded as an audit receipt.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .legacy_yaml import AssociationValues, LegacyStoreRecord, LegacyUserRecord


@dataclass(frozen=True, slots=True)
class AssociationSnapshot:
    """One ordered tag/sticker association in a migration snapshot."""

    tag: str
    sticker_id: str
    position: int

    def as_dict(self) -> dict[str, str | int]:
        return {"tag": self.tag, "sticker_id": self.sticker_id, "position": self.position}


@dataclass(frozen=True, slots=True)
class UserSnapshot:
    """Canonical state for one regular user."""

    telegram_id: int
    private_mode: bool
    shuffle: bool
    stickers: tuple[AssociationSnapshot, ...]
    cached_stickers: tuple[AssociationSnapshot, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "telegram_id": self.telegram_id,
            "private_mode": self.private_mode,
            "shuffle": self.shuffle,
            "stickers": [item.as_dict() for item in self.stickers],
            "cached_stickers": [item.as_dict() for item in self.cached_stickers],
        }


@dataclass(frozen=True, slots=True)
class PackSnapshot:
    """Canonical state for the shared public pack."""

    stickers: tuple[AssociationSnapshot, ...]
    cached_stickers: tuple[AssociationSnapshot, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "stickers": [item.as_dict() for item in self.stickers],
            "cached_stickers": [item.as_dict() for item in self.cached_stickers],
        }


@dataclass(frozen=True, slots=True)
class LogicalPersistenceSnapshot:
    """Canonical representation used to compare migration source and target.

    Keep this type free of SQLAlchemy and domain objects: migration verification
    should compare logical data rather than backend-specific row identities.
    """

    users: tuple[UserSnapshot, ...]
    public_pack: PackSnapshot

    def as_dict(self) -> dict[str, object]:
        return {
            "users": [user.as_dict() for user in self.users],
            "public_pack": self.public_pack.as_dict(),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def snapshot_from_legacy(store: LegacyStoreRecord) -> LogicalPersistenceSnapshot:
    """Build a canonical snapshot from validated legacy records."""
    users = tuple(
        sorted(
            (_user_snapshot(int(user.identifier), user) for user in store.users),
            key=lambda item: item.telegram_id,
        )
    )
    public = _pack_snapshot(store.public_pack) if store.public_pack else _empty_pack()
    return LogicalPersistenceSnapshot(users, public)


def snapshot_from_records(
    users: tuple[LegacyUserRecord, ...],
    public_pack: LegacyUserRecord | None,
) -> LogicalPersistenceSnapshot:
    """Build a canonical snapshot from records projected by a migration gateway."""
    return snapshot_from_legacy(LegacyStoreRecord(users, public_pack))


def _user_snapshot(user_id: int, user: LegacyUserRecord) -> UserSnapshot:
    return UserSnapshot(
        telegram_id=user_id,
        private_mode=bool(user.private_mode),
        shuffle=bool(user.shuffle),
        stickers=_associations(user.stickers),
        cached_stickers=_associations(user.cached_stickers),
    )


def _pack_snapshot(pack: LegacyUserRecord) -> PackSnapshot:
    return PackSnapshot(
        stickers=_associations(pack.stickers),
        cached_stickers=_associations(pack.cached_stickers),
    )


def _empty_pack() -> PackSnapshot:
    return PackSnapshot((), ())


def _associations(values: AssociationValues) -> tuple[AssociationSnapshot, ...]:
    result = [
        AssociationSnapshot(tag, sticker_id, position)
        for tag, sticker_ids in values
        for position, sticker_id in enumerate(sticker_ids)
    ]
    return tuple(sorted(result, key=lambda item: (item.tag, item.position, item.sticker_id)))
