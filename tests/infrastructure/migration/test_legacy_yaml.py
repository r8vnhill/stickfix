"""Tests for the restricted legacy YAML projection."""

# The repository's test suite uses plain assertions for readable contract checks.
# ruff: noqa: S101

from __future__ import annotations

import pytest
import yaml

from bot.domain.user import SF_PUBLIC, StickfixUser
from bot.infrastructure.migration.legacy_yaml import LegacyYamlError, load_legacy_yaml
from bot.infrastructure.migration.logical_snapshot import (
    snapshot_from_mapping,
)


def test_legacy_loader_reads_supported_users_and_public_pack(tmp_path) -> None:
    user = StickfixUser(123)
    user.private_mode = True
    user.shuffle = True
    user.stickers = {"wave": ["sticker-1", "sticker-2"]}
    user.cached_stickers = {"wave": ["sticker-2"]}
    public = StickfixUser(SF_PUBLIC)
    public.stickers = {"public": ["sticker-3"]}
    source = tmp_path / "users.yaml"
    with source.open("w", encoding="utf-8") as handle:
        yaml.dump({123: user, SF_PUBLIC: public}, handle, Dumper=yaml.Dumper)

    loaded = load_legacy_yaml(source)
    snapshot = snapshot_from_mapping(loaded)

    assert snapshot.users[0]["telegram_id"] == 123
    assert snapshot.users[0]["private_mode"] is True
    assert snapshot.users[0]["cached_stickers"][0]["sticker_id"] == "sticker-2"
    assert snapshot.public_pack["stickers"][0]["sticker_id"] == "sticker-3"


def test_legacy_loader_rejects_unknown_python_objects(tmp_path) -> None:
    source = tmp_path / "users.yaml"
    source.write_text(
        "123: !!python/object:os.path.WindowsPath {}\n",
        encoding="utf-8",
    )

    with pytest.raises(LegacyYamlError):
        load_legacy_yaml(source)


def test_logical_snapshot_is_independent_of_mapping_and_tag_order() -> None:
    first = StickfixUser(123)
    first.stickers = {"z": ["b", "a"], "a": ["c"]}
    second = StickfixUser(123)
    second.stickers = {"a": ["c"], "z": ["b", "a"]}

    first_snapshot = snapshot_from_mapping({123: first})
    second_snapshot = snapshot_from_mapping({123: second})

    assert first_snapshot.as_dict() == second_snapshot.as_dict()
    assert first_snapshot.sha256() == second_snapshot.sha256()
