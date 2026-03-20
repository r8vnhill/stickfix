"""Persistence and recovery tests for the YAML-backed `StickfixDB` store."""

from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path
from typing import Any

import pytest
import yaml

from bot.database.storage import StickfixDB
from tests.support.storage import (
    assert_store_keys,
    assert_store_matches,
    assert_user_matches,
    create_user,
    expected_snapshot,
    load_snapshot,
    make_user_spec,
    store_snapshot,
    write_snapshot,
    write_valid_or_invalid,
)


def test_save_load_roundtrip_and_overwrite_preserve_logical_contents(
    store: StickfixDB, tmp_path: Path
) -> None:
    original = create_user("alice")
    replacement = create_user("alice", private_mode=True, shuffle=True, tags=("wave", "spark"))

    store["alice"] = original
    store.save()
    store["alice"] = replacement
    store.save()

    reloaded = StickfixDB("users", data_dir=tmp_path)

    assert_store_keys(reloaded, {"alice"})
    assert_user_matches(reloaded["alice"], replacement)


def test_reload_is_idempotent_when_file_is_unchanged(store: StickfixDB) -> None:
    store["alice"] = create_user("alice", shuffle=True)
    store.save()
    first_snapshot = store_snapshot(store)

    store.reload()
    second_snapshot = store_snapshot(store)
    store.reload()

    assert store_snapshot(store) == first_snapshot
    assert second_snapshot == first_snapshot


def test_save_rotates_backups_in_order(
    store: StickfixDB, store_paths: tuple[Path, Path, Path]
) -> None:
    yaml_path, bak1, bak2 = store_paths

    store["first"] = create_user("first")
    store.save()
    first_snapshot = load_snapshot(yaml_path)

    store["second"] = create_user("second")
    store.save()
    second_snapshot = load_snapshot(yaml_path)

    store["third"] = create_user("third")
    store.save()

    assert bak1.exists()
    assert bak2.exists()
    assert load_snapshot(bak1) == second_snapshot
    assert load_snapshot(bak2) == first_snapshot


@pytest.mark.parametrize(
    ("main_valid", "bak1_valid", "bak2_valid", "expected_source"),
    [
        (False, True, True, "bak1"),
        (False, False, True, "bak2"),
    ],
    ids=["recover-bak1", "recover-bak2"],
)
def test_load_recovers_from_newest_readable_backup(
    tmp_path: Path,
    store_paths: tuple[Path, Path, Path],
    main_valid: bool,
    bak1_valid: bool,
    bak2_valid: bool,
    expected_source: str,
) -> None:
    yaml_path, bak1, bak2 = store_paths
    snapshots = {
        "main": {"main": make_user_spec(tags=("main",))},
        "bak1": {"backup-one": make_user_spec(private_mode=True)},
        "bak2": {"backup-two": make_user_spec(shuffle=True)},
    }

    write_valid_or_invalid(yaml_path, snapshots["main"], valid=main_valid)
    write_valid_or_invalid(bak1, snapshots["bak1"], valid=bak1_valid)
    write_valid_or_invalid(bak2, snapshots["bak2"], valid=bak2_valid)

    store = StickfixDB("users", data_dir=tmp_path)
    expected = expected_snapshot(snapshots[expected_source])

    assert_store_matches(store, expected)
    assert load_snapshot(yaml_path) == expected


def test_load_recovers_from_backup_when_main_read_raises_os_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    store_paths: tuple[Path, Path, Path],
) -> None:
    yaml_path, bak1, _ = store_paths
    expected_specs = {"alice": make_user_spec()}
    write_snapshot(yaml_path, {})
    write_snapshot(bak1, expected_specs)
    original_open = Path.open

    def flaky_open(path_obj: Path, *args: Any, **kwargs: Any):
        if path_obj == yaml_path:
            raise OSError("main file unavailable")
        return original_open(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "open", flaky_open)

    store = StickfixDB("users", data_dir=tmp_path)

    assert_store_matches(store, expected_snapshot(expected_specs))


def test_reload_raises_runtime_error_when_all_snapshots_are_unreadable(
    tmp_path: Path,
    store_paths: tuple[Path, Path, Path],
) -> None:
    for path in store_paths:
        path.write_text("invalid: [yaml", encoding="utf-8")

    with pytest.raises(RuntimeError):
        StickfixDB("users", data_dir=tmp_path)


@pytest.mark.parametrize("failure_mode", ["replace", "temp-validation"])
def test_save_is_atomic_on_failure(
    store: StickfixDB,
    store_paths: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    yaml_path, _, _ = store_paths
    store["first"] = create_user("first")
    store.save()
    original_snapshot = load_snapshot(yaml_path)
    store["second"] = create_user("second")

    if failure_mode == "replace":

        def broken_replace(_src: Path | str, _dst: Path | str) -> None:
            raise OSError("replace failed")

        monkeypatch.setattr("bot.database.storage.os.replace", broken_replace)
        expected_error = OSError
    else:
        # noinspection PyProtectedMember
        original_validate = StickfixDB._load_path

        def broken_validate(path: Path) -> dict[str, Any]:
            if path != yaml_path:
                raise yaml.YAMLError("temp validation failed")
            return original_validate(path)

        monkeypatch.setattr(StickfixDB, "_load_path", staticmethod(broken_validate))
        expected_error = yaml.YAMLError

    with pytest.raises(expected_error):
        store.save()

    assert load_snapshot(yaml_path) == original_snapshot
    reloaded = StickfixDB("users", data_dir=yaml_path.parent)
    assert_store_keys(reloaded, {"first"})
