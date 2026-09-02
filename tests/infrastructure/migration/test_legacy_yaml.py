"""Contract tests for the restricted, domain-independent legacy YAML projection.

Fixtures retain historical object tags while asserting immutable records and
canonical snapshots independent of YAML mapping order.
"""

# The repository's test suite uses plain assertions for readable contract checks.
# ruff: noqa: S101

from __future__ import annotations

import sys

import pytest

from bot.infrastructure.migration.legacy_yaml import (
    LegacyUserRecord,
    LegacyYamlError,
    load_legacy_yaml,
)
from bot.infrastructure.migration.logical_snapshot import snapshot_from_legacy

USER_AND_PUBLIC_YAML = """123: !<tag:yaml.org,2002:python/object:bot.domain.user.StickfixUser>
  id: 123
  private_mode: true
  _shuffle: true
  stickers:
    wave: [sticker-1, sticker-2]
  cached_stickers:
    wave: [sticker-2]
SF-PUBLIC: !<tag:yaml.org,2002:python/object:bot.database.users.StickfixUser>
  id: SF-PUBLIC
  stickers:
    public: [sticker-3]
"""
ORDERED_YAML = (
    "123: !<tag:yaml.org,2002:python/object:bot.domain.user.StickfixUser>\n"
    "  id: 123\n"
    "  stickers:\n"
    "    {tag_a}: [{stickers_a}]\n"
    "    {tag_b}: [{stickers_b}]\n"
)


def _write_yaml(path, content: str):
    path.write_text(content, encoding="utf-8")
    return path


def test_legacy_loader_reads_supported_users_and_public_pack(tmp_path) -> None:
    source = _write_yaml(tmp_path / "users.yaml", USER_AND_PUBLIC_YAML)

    loaded = load_legacy_yaml(source)
    snapshot = snapshot_from_legacy(loaded)

    assert loaded.users == (
        LegacyUserRecord(
            identifier=123,
            private_mode=True,
            shuffle=True,
            stickers=(("wave", ("sticker-1", "sticker-2")),),
            cached_stickers=(("wave", ("sticker-2",)),),
        ),
    )
    assert snapshot.users[0].telegram_id == 123
    assert snapshot.users[0].cached_stickers[0].sticker_id == "sticker-2"
    assert snapshot.public_pack.stickers[0].sticker_id == "sticker-3"


def test_legacy_loader_does_not_import_or_instantiate_historical_classes(tmp_path) -> None:
    source = _write_yaml(
        tmp_path / "users.yaml",
        """123: !<tag:yaml.org,2002:python/object:bot.domain.user.StickfixUser>
  id: 123
""",
    )

    load_legacy_yaml(source)

    assert "bot.database" not in sys.modules


def test_legacy_loader_rejects_unknown_python_objects(tmp_path) -> None:
    source = _write_yaml(tmp_path / "users.yaml", "123: !!python/object:os.path.WindowsPath {}\n")

    with pytest.raises(LegacyYamlError):
        load_legacy_yaml(source)


def test_logical_snapshot_is_independent_of_mapping_and_tag_order(tmp_path) -> None:
    first = _write_yaml(
        tmp_path / "first.yaml",
        ORDERED_YAML.format(tag_a="z", stickers_a="b, a", tag_b="a", stickers_b="c"),
    )
    second = _write_yaml(
        tmp_path / "second.yaml",
        ORDERED_YAML.format(tag_a="a", stickers_a="c", tag_b="z", stickers_b="b, a"),
    )

    first_snapshot = snapshot_from_legacy(load_legacy_yaml(first))
    second_snapshot = snapshot_from_legacy(load_legacy_yaml(second))

    assert first_snapshot.as_dict() == second_snapshot.as_dict()
    assert first_snapshot.sha256() == second_snapshot.sha256()
