"""Property-based invariants for the YAML-backed `StickfixDB` store."""

from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import assume, settings
from hypothesis import given as hypothesis_given
from hypothesis import strategies as st

from bot.database.storage import StickfixDB
from tests.support.storage import (
    OPERATION_STRATEGY,
    STORE_DATA_STRATEGY,
    UserSnapshot,
    UserSpec,
    assert_store_matches,
    create_user_from_spec,
    expected_snapshot,
    load_snapshot,
    make_user_spec,
    user_snapshot,
    write_valid_or_invalid,
)


@hypothesis_given(operations=OPERATION_STRATEGY)
def test_mapping_behavior_matches_reference_dict(
    operations: list[tuple[str, str, UserSpec | None]],
) -> None:
    with TemporaryDirectory() as tmp_dir:
        store = StickfixDB("users", data_dir=Path(tmp_dir))
        reference: dict[str, UserSnapshot] = {}

        for action, key, payload in operations:
            if action == "set":
                assert payload is not None
                store[key] = create_user_from_spec(key, payload)
                reference[key] = user_snapshot(create_user_from_spec(key, payload))
            else:
                if key in reference:
                    del store[key]
                    del reference[key]
                else:
                    with pytest.raises(KeyError):
                        del store[key]

            assert_store_matches(store, reference)


@settings(deadline=None)
@hypothesis_given(specs=STORE_DATA_STRATEGY)
def test_save_reload_roundtrip_preserves_logical_contents(specs: dict[str, UserSpec]) -> None:
    with TemporaryDirectory() as tmp_dir:
        data_dir = Path(tmp_dir)
        store = StickfixDB("users", data_dir=data_dir)

        for key, spec in specs.items():
            store[key] = create_user_from_spec(key, spec)
        store.save()

        reloaded = StickfixDB("users", data_dir=data_dir)

        assert_store_matches(reloaded, expected_snapshot(specs))


@settings(deadline=None)
@hypothesis_given(specs=STORE_DATA_STRATEGY)
def test_save_is_idempotent_for_arbitrary_store_contents(specs: dict[str, UserSpec]) -> None:
    with TemporaryDirectory() as tmp_dir:
        data_dir = Path(tmp_dir)
        store = StickfixDB("users", data_dir=data_dir)

        for key, spec in specs.items():
            store[key] = create_user_from_spec(key, spec)
        store.save()
        first_persisted_snapshot = load_snapshot(data_dir / "users.yaml")

        store.reload()
        store.save()
        reloaded = StickfixDB("users", data_dir=data_dir)

        assert_store_matches(reloaded, expected_snapshot(specs))
        assert load_snapshot(data_dir / "users.yaml") == first_persisted_snapshot


@settings(deadline=None)
@hypothesis_given(bak1_valid=st.booleans(), bak2_valid=st.booleans())
def test_recovery_prefers_first_readable_backup_property(
    bak1_valid: bool,
    bak2_valid: bool,
) -> None:
    assume(bak1_valid or bak2_valid)
    with TemporaryDirectory() as tmp_dir:
        data_dir = Path(tmp_dir)
        yaml_path = data_dir / "users.yaml"
        bak1 = data_dir / "users.yaml_1.bak"
        bak2 = data_dir / "users.yaml_2.bak"
        snapshots = {
            "bak1": {"backup-one": make_user_spec(private_mode=True)},
            "bak2": {"backup-two": make_user_spec(shuffle=True)},
        }

        yaml_path.write_text("invalid: [yaml", encoding="utf-8")
        write_valid_or_invalid(bak1, snapshots["bak1"], valid=bak1_valid)
        write_valid_or_invalid(bak2, snapshots["bak2"], valid=bak2_valid)

        store = StickfixDB("users", data_dir=data_dir)
        expected_key = "bak1" if bak1_valid else "bak2"

        assert_store_matches(store, expected_snapshot(snapshots[expected_key]))
        assert load_snapshot(yaml_path) == expected_snapshot(snapshots[expected_key])
