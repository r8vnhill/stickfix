"""Mapping-contract tests for the YAML-backed `StickfixDB` store."""

from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path

import pytest

from bot.database.storage import StickfixDB
from tests.support.storage import (
    assert_store_keys,
    assert_store_matches,
    assert_user_matches,
    create_user,
    expected_snapshot,
    make_user_spec,
)


@pytest.mark.parametrize("directory_exists", [False, True], ids=["missing-dir", "existing-dir"])
def test_init_creates_missing_storage_artifacts(tmp_path: Path, directory_exists: bool) -> None:
    data_dir = tmp_path / "data"
    if directory_exists:
        data_dir.mkdir()

    store = StickfixDB("users", data_dir=data_dir)

    assert data_dir.exists()
    assert (data_dir / "users.yaml").exists()
    assert len(store) == 0
    assert_store_matches(store, {})


@pytest.mark.parametrize("contents", ["", "{}\n"], ids=["empty-doc", "empty-mapping"])
def test_empty_like_yaml_loads_as_empty_store(tmp_path: Path, contents: str) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "users.yaml").write_text(contents, encoding="utf-8")

    store = StickfixDB("users", data_dir=data_dir)

    assert len(store) == 0
    assert_store_matches(store, {})


def test_store_exposes_mapping_views(store: StickfixDB) -> None:
    alice = create_user("alice")
    bob = create_user("bob", private_mode=True)
    store["alice"] = alice
    store["bob"] = bob

    assert set(store.keys()) == {"alice", "bob"}
    assert list(store.values()) == [alice, bob]
    assert dict(store.items()) == {"alice": alice, "bob": bob}
    assert list(iter(store)) == ["alice", "bob"]
    assert store.get("missing") is None


def test_store_supports_higher_level_mutable_mapping_operations(store: StickfixDB) -> None:
    alice = create_user("alice")
    bob = create_user("bob")
    charlie = create_user("charlie", shuffle=True)
    dana = create_user("dana", private_mode=True)
    default_user = create_user("default")

    store["alice"] = alice
    store["bob"] = bob

    popped = store.pop("alice")
    assert_user_matches(popped, alice)
    assert_store_keys(store, {"bob"})

    existing = store.setdefault("bob", default_user)
    assert_user_matches(existing, bob)
    inserted = store.setdefault("charlie", charlie)
    assert_user_matches(inserted, charlie)

    store.update({"dana": dana})
    assert_store_matches(
        store,
        expected_snapshot(
            {
                "bob": make_user_spec(),
                "charlie": make_user_spec(shuffle=True),
                "dana": make_user_spec(private_mode=True),
            }
        ),
    )

    store.clear()
    assert not list(store.keys())
    assert_store_matches(store, {})


def test_missing_key_operations_raise_key_error(store: StickfixDB) -> None:
    with pytest.raises(KeyError):
        _ = store["missing"]

    with pytest.raises(KeyError):
        del store["missing"]


def test_mutations_are_not_persisted_until_save(tmp_path: Path) -> None:
    store = StickfixDB("users", data_dir=tmp_path)
    store["alice"] = create_user("alice")

    reloaded = StickfixDB("users", data_dir=tmp_path)

    assert "alice" not in reloaded
