"""Backend-independent, deterministic persistence snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from bot.application.ports import PublicPackRepository, UserRepository
from bot.domain.identifiers import UserId
from bot.domain.user import SF_PUBLIC, StickfixUser


@dataclass(frozen=True, slots=True)
class LogicalPersistenceSnapshot:
    """Canonical representation used to compare YAML and PostgreSQL state."""

    users: tuple[dict[str, Any], ...]
    public_pack: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"users": list(self.users), "public_pack": self.public_pack}

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def snapshot_from_mapping(
    users: dict[object, StickfixUser],
) -> LogicalPersistenceSnapshot:
    regular: list[dict[str, Any]] = []
    public: dict[str, Any] = {"stickers": [], "cached_stickers": []}
    for key, user in users.items():
        if key == SF_PUBLIC or user.id == SF_PUBLIC:
            public = _pack_snapshot(user)
            continue
        user_id = int(str(key))
        regular.append(_user_snapshot(user_id, user))
    regular.sort(key=lambda item: item["telegram_id"])
    return LogicalPersistenceSnapshot(tuple(regular), public)


def snapshot_from_repository(
    users: UserRepository,
    public: PublicPackRepository,
) -> LogicalPersistenceSnapshot:
    """Project an infrastructure repository through its public read contract."""
    user_ids = users.iter_user_ids()  # type: ignore[attr-defined]
    mapping = {user_id: users.get_user(UserId(user_id)) for user_id in user_ids}
    normalized = {key: value for key, value in mapping.items() if value is not None}
    public_pack = public.get()
    if public_pack is not None:
        normalized[SF_PUBLIC] = public_pack
    return snapshot_from_mapping(normalized)


def _user_snapshot(user_id: int, user: StickfixUser) -> dict[str, Any]:
    return {
        "telegram_id": user_id,
        "private_mode": bool(user.private_mode),
        "shuffle": bool(user.shuffle),
        "stickers": _associations(user.stickers),
        "cached_stickers": _associations(user.cached_stickers),
    }


def _pack_snapshot(pack: StickfixUser) -> dict[str, Any]:
    return {
        "stickers": _associations(pack.stickers),
        "cached_stickers": _associations(pack.cached_stickers),
    }


def _associations(values: dict[str, list[str]]) -> list[dict[str, Any]]:
    result = [
        {"tag": tag, "sticker_id": sticker_id, "position": position}
        for tag, sticker_ids in values.items()
        for position, sticker_id in enumerate(sticker_ids)
    ]
    return sorted(result, key=lambda item: (item["tag"], item["position"], item["sticker_id"]))
