"""Restricted reader for the historical Python-object YAML format."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bot.domain.user import StickfixUser


class LegacyYamlError(ValueError):
    """Raised when a legacy YAML document is not safe or not supported."""


class _LegacyLoader(yaml.SafeLoader):
    pass


def _construct_user(loader: yaml.Loader, node: yaml.Node) -> StickfixUser:
    state = loader.construct_mapping(node, deep=True)
    if "id" not in state:
        raise LegacyYamlError("legacy StickfixUser is missing id")
    user = StickfixUser(state["id"])
    user.private_mode = bool(state.get("private_mode", False))
    user.shuffle = bool(state.get("_shuffle", state.get("shuffle", False)))
    user.stickers = _mapping_of_lists(state.get("stickers", {}), "stickers")
    user.cached_stickers = _mapping_of_lists(state.get("cached_stickers", {}), "cached_stickers")
    return user


def _mapping_of_lists(value: Any, field: str) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise LegacyYamlError(f"{field} must be a mapping")
    result: dict[str, list[str]] = {}
    for tag, sticker_ids in value.items():
        if not isinstance(tag, str) or not isinstance(sticker_ids, list):
            raise LegacyYamlError(f"{field} contains an invalid association")
        if not all(isinstance(sticker_id, str) and sticker_id for sticker_id in sticker_ids):
            raise LegacyYamlError(f"{field} contains a non-string sticker id")
        if len(sticker_ids) != len(set(sticker_ids)):
            raise LegacyYamlError(f"{field} contains duplicate sticker associations")
        result[tag] = list(sticker_ids)
    return result


for _tag in (
    "tag:yaml.org,2002:python/object:bot.domain.user.StickfixUser",
    "tag:yaml.org,2002:python/object:bot.database.users.StickfixUser",
):
    _LegacyLoader.add_constructor(_tag, _construct_user)


def load_legacy_yaml(path: Path) -> dict[object, StickfixUser]:
    """Load only the two known StickfixUser YAML tags."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = yaml.load(handle, Loader=_LegacyLoader)  # noqa: S506
    except (OSError, yaml.YAMLError) as error:
        raise LegacyYamlError(f"could not read legacy YAML: {path}") from error
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise LegacyYamlError("legacy YAML root must be a mapping")
    _validate_keys_and_values(value)
    return value


def _validate_keys_and_values(value: dict[object, Any]) -> None:
    seen_ids: set[int] = set()
    public_seen = False
    for key, user in value.items():
        if not isinstance(user, StickfixUser):
            raise LegacyYamlError(f"unsupported object for key {key!r}")
        if str(key) == "SF-PUBLIC" or user.id == "SF-PUBLIC":
            if public_seen:
                raise LegacyYamlError("legacy YAML contains multiple public packs")
            public_seen = True
            continue
        try:
            user_id = int(str(key))
            object_id = int(str(user.id))
        except (TypeError, ValueError) as error:
            raise LegacyYamlError(f"user id {key!r} is not numeric") from error
        if user_id != object_id:
            raise LegacyYamlError(f"user id mismatch for key {key!r}")
        if user_id in seen_ids:
            raise LegacyYamlError(f"duplicate user id {user_id}")
        seen_ids.add(user_id)
