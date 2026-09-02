"""Project the historical Python-object YAML format into safe value records.

Only the two class-tag strings emitted by older Stickfix versions are accepted.
Their payloads are converted into immutable records immediately; the named Python
classes are never imported or instantiated. This module is migration input code,
not a runtime persistence adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class LegacyYamlError(ValueError):
    """Raised when a legacy YAML document is not safe or not supported."""


class _LegacyLoader(yaml.SafeLoader):
    pass


AssociationValues = tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True, slots=True)
class LegacyUserRecord:
    """Immutable, domain-independent representation of one legacy user entry.

    ``identifier`` remains a string for the historical ``SF-PUBLIC`` record and
    is numeric for regular users. The logical snapshot layer performs the explicit
    conversion required by the runtime PostgreSQL schema.
    """

    identifier: int | str
    private_mode: bool
    shuffle: bool
    stickers: AssociationValues
    cached_stickers: AssociationValues


@dataclass(frozen=True, slots=True)
class LegacyStoreRecord:
    """Validated legacy store contents, independent of live domain classes.

    The public pack is separated here so downstream migration code never needs to
    treat ``SF-PUBLIC`` as a synthetic runtime user.
    """

    users: tuple[LegacyUserRecord, ...]
    public_pack: LegacyUserRecord | None = None


def _construct_user(loader: yaml.Loader, node: yaml.Node) -> LegacyUserRecord:
    state = loader.construct_mapping(node, deep=True)
    if "id" not in state:
        raise LegacyYamlError("legacy StickfixUser is missing id")
    return LegacyUserRecord(
        identifier=state["id"],
        private_mode=bool(state.get("private_mode", False)),
        shuffle=bool(state.get("_shuffle", state.get("shuffle", False))),
        stickers=_mapping_of_lists(state.get("stickers", {}), "stickers"),
        cached_stickers=_mapping_of_lists(state.get("cached_stickers", {}), "cached_stickers"),
    )


def _mapping_of_lists(value: Any, field: str) -> AssociationValues:
    if not isinstance(value, dict):
        raise LegacyYamlError(f"{field} must be a mapping")
    result: list[tuple[str, tuple[str, ...]]] = []
    for tag, sticker_ids in value.items():
        if not isinstance(tag, str) or not isinstance(sticker_ids, list):
            raise LegacyYamlError(f"{field} contains an invalid association")
        if not all(isinstance(sticker_id, str) and sticker_id for sticker_id in sticker_ids):
            raise LegacyYamlError(f"{field} contains a non-string sticker id")
        if len(sticker_ids) != len(set(sticker_ids)):
            raise LegacyYamlError(f"{field} contains duplicate sticker associations")
        result.append((tag, tuple(sticker_ids)))
    return tuple(result)


for _tag in (
    "tag:yaml.org,2002:python/object:bot.domain.user.StickfixUser",
    "tag:yaml.org,2002:python/object:bot.database.users.StickfixUser",
):
    _LegacyLoader.add_constructor(_tag, _construct_user)


def load_legacy_yaml(path: Path) -> LegacyStoreRecord:
    """Read and validate one historical YAML file without executing object code.

    Empty files produce an empty store. Invalid roots, unknown Python-object tags,
    mismatched user ids, duplicate associations, and duplicate public packs raise
    :class:`LegacyYamlError` before any PostgreSQL adapter is called.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = yaml.load(handle, Loader=_LegacyLoader)  # noqa: S506
    except (OSError, yaml.YAMLError) as error:
        raise LegacyYamlError(f"could not read legacy YAML: {path}") from error
    if value is None:
        return LegacyStoreRecord(())
    if not isinstance(value, dict):
        raise LegacyYamlError("legacy YAML root must be a mapping")
    return _validate_keys_and_values(value)


def _validate_keys_and_values(value: dict[object, Any]) -> LegacyStoreRecord:
    seen_ids: set[int] = set()
    users: list[LegacyUserRecord] = []
    public_pack: LegacyUserRecord | None = None
    for key, user in value.items():
        _require_user_record(key, user)
        if _is_public_record(key, user):
            public_pack = _select_public_pack(public_pack, user)
            continue
        users.append(_numeric_user(key, user, seen_ids))
    return LegacyStoreRecord(tuple(users), public_pack)


def _require_user_record(key: object, user: object) -> None:
    if not isinstance(user, LegacyUserRecord):
        raise LegacyYamlError(f"unsupported object for key {key!r}")


def _is_public_record(key: object, user: LegacyUserRecord) -> bool:
    return str(key) == "SF-PUBLIC" or user.identifier == "SF-PUBLIC"


def _select_public_pack(
    current: LegacyUserRecord | None,
    candidate: LegacyUserRecord,
) -> LegacyUserRecord:
    if current is not None:
        raise LegacyYamlError("legacy YAML contains multiple public packs")
    return candidate


def _numeric_user(
    key: object,
    user: LegacyUserRecord,
    seen_ids: set[int],
) -> LegacyUserRecord:
    try:
        user_id = int(str(key))
        object_id = int(str(user.identifier))
    except (TypeError, ValueError) as error:
        raise LegacyYamlError(f"user id {key!r} is not numeric") from error
    if user_id != object_id:
        raise LegacyYamlError(f"user id mismatch for key {key!r}")
    if user_id in seen_ids:
        raise LegacyYamlError(f"duplicate user id {user_id}")
    seen_ids.add(user_id)
    return LegacyUserRecord(
        identifier=user_id,
        private_mode=user.private_mode,
        shuffle=user.shuffle,
        stickers=user.stickers,
        cached_stickers=user.cached_stickers,
    )
