"""Shared factories, assertions, and generated inputs for storage tests."""

from __future__ import annotations

import string
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from hamcrest import assert_that, is_
from hypothesis import strategies as st

from bot.database.storage import StickfixDB
from bot.domain.user import StickfixUser

UserSpec = dict[str, Any]
UserSnapshot = dict[str, Any]


def create_user(
    user_id: str,
    *,
    private_mode: bool = False,
    shuffle: bool = False,
    tags: tuple[str, ...] = ("wave",),
) -> StickfixUser:
    """Create a minimal `StickfixUser` suitable for storage-focused tests."""
    user = StickfixUser(user_id)
    user.private_mode = private_mode
    user.shuffle = shuffle
    user.add_sticker(f"{user_id}-sticker", list(tags))
    return user


def make_user_spec(
    *,
    private_mode: bool = False,
    shuffle: bool = False,
    tags: tuple[str, ...] = ("wave",),
) -> UserSpec:
    """Build a compact logical description of one persisted user."""
    return {
        "private_mode": private_mode,
        "shuffle": shuffle,
        "tags": tags,
    }


def create_user_from_spec(user_id: str, spec: UserSpec) -> StickfixUser:
    """Materialize one `StickfixUser` from a generated or reference spec."""
    return create_user(
        user_id,
        private_mode=bool(spec["private_mode"]),
        shuffle=bool(spec["shuffle"]),
        tags=tuple(spec["tags"]),
    )


def user_snapshot(user: StickfixUser) -> UserSnapshot:
    """Normalize one user into the storage fields these tests care about."""
    return {
        "private_mode": user.private_mode,
        "shuffle": user.shuffle,
        "stickers": dict(user.stickers),
    }


def store_snapshot(source: Mapping[str, StickfixUser]) -> dict[str, UserSnapshot]:
    """Normalize one mapping of users into logical snapshots."""
    return {key: user_snapshot(value) for key, value in source.items()}


def expected_snapshot(specs: Mapping[str, UserSpec]) -> dict[str, UserSnapshot]:
    """Build the normalized store state expected from logical user specs."""
    return {key: user_snapshot(create_user_from_spec(key, spec)) for key, spec in specs.items()}


def dump_store(path: Path, data: Mapping[str, StickfixUser]) -> None:
    """Write a raw YAML snapshot for controlled persistence/recovery setup."""
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(dict(data), handle, yaml.Dumper)


def write_snapshot(path: Path, specs: Mapping[str, UserSpec]) -> None:
    """Write one valid YAML snapshot from logical user specifications."""
    dump_store(path, {key: create_user_from_spec(key, spec) for key, spec in specs.items()})


def write_valid_or_invalid(path: Path, specs: Mapping[str, UserSpec], *, valid: bool) -> None:
    """Write either a readable snapshot or an intentionally corrupt YAML file."""
    if valid:
        write_snapshot(path, specs)
        return
    path.write_text("invalid: [yaml", encoding="utf-8")


def assert_store_keys(store: StickfixDB, expected: set[str]) -> None:
    """Assert that the store exposes exactly the expected key set."""
    assert_that(set(store.get_keys()), is_(expected))


def assert_user_matches(actual: StickfixUser, expected: StickfixUser) -> None:
    """Assert that two users match logically for persistence purposes."""
    assert_that(user_snapshot(actual), is_(user_snapshot(expected)))


def assert_store_matches(
    store: Mapping[str, StickfixUser], expected: Mapping[str, UserSnapshot]
) -> None:
    """Assert that a store matches the expected logical contents."""
    assert_that(store_snapshot(store), is_(dict(expected)))


def load_snapshot(path: Path) -> dict[str, UserSnapshot]:
    """Load and normalize one persisted YAML snapshot for assertions."""
    # noinspection PyProtectedMember
    return store_snapshot(StickfixDB._load_path(path))


USER_ID_STRATEGY = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=6)
USER_SPEC_STRATEGY = st.builds(
    make_user_spec,
    private_mode=st.booleans(),
    shuffle=st.booleans(),
    tags=st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=6),
        min_size=1,
        max_size=3,
        unique=True,
    ).map(tuple),
)
STORE_DATA_STRATEGY = st.dictionaries(
    keys=USER_ID_STRATEGY,
    values=USER_SPEC_STRATEGY,
    min_size=0,
    max_size=5,
)
OPERATION_STRATEGY = st.lists(
    st.one_of(
        st.tuples(st.just("set"), USER_ID_STRATEGY, USER_SPEC_STRATEGY),
        st.tuples(st.just("delete"), USER_ID_STRATEGY, st.none()),
    ),
    min_size=1,
    max_size=20,
)
