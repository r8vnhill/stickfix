"""PostgreSQL repository contract tests.

These tests are opt-in because they intentionally clear the explicitly supplied test database.
"""

# The repository's test suite uses plain assertions for readable contract checks.
# ruff: noqa: S101

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from bot.domain.identifiers import UserId
from bot.domain.user import StickfixUser
from bot.infrastructure.persistence.postgres import (
    PostgresUserRepository,
    create_engine_and_session_factory,
)

DATABASE_URL = os.environ.get("STICKFIX_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture
def postgres_repository():
    if not DATABASE_URL:
        pytest.skip("set STICKFIX_TEST_DATABASE_URL to run PostgreSQL contract tests")
    engine, factory = create_engine_and_session_factory(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, public_sticker_tags, public_cached_stickers, "
                "user_sticker_tags, user_cached_stickers, stickers, tags "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield PostgresUserRepository(factory)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, public_sticker_tags, public_cached_stickers, "
                "user_sticker_tags, user_cached_stickers, stickers, tags "
                "RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()


def test_user_and_public_pack_round_trip(postgres_repository) -> None:
    user = StickfixUser(UserId(123))
    user.private_mode = True
    user.shuffle = True
    user.stickers = {"wave": ["s1", "s2"]}
    user.cached_stickers = {"wave": ["s2", "s3"]}
    public = StickfixUser("SF-PUBLIC")
    public.stickers = {"public": ["s4"]}
    public.cached_stickers = {"public": ["s5"]}

    postgres_repository.save_user(user)
    postgres_repository.save(public)

    loaded_user = postgres_repository.get_user(UserId(123))
    loaded_public = postgres_repository.get()
    assert loaded_user is not None
    assert loaded_user.private_mode is True
    assert loaded_user.shuffle is True
    assert loaded_user.stickers == user.stickers
    assert loaded_user.cached_stickers == user.cached_stickers
    assert loaded_public is not None
    assert loaded_public.stickers == public.stickers
    assert loaded_public.cached_stickers == public.cached_stickers


def test_failed_user_mutation_rolls_back(postgres_repository) -> None:
    user = StickfixUser(UserId(123))
    user.stickers = {"wave": ["s1"]}
    postgres_repository.save_user(user)

    invalid = StickfixUser(UserId(123))
    invalid.stickers = {"wave": [None]}  # type: ignore[list-item]
    with pytest.raises((TypeError, ValueError, IntegrityError)):
        postgres_repository.save_user(invalid)

    loaded = postgres_repository.get_user(UserId(123))
    assert loaded is not None
    assert loaded.stickers == {"wave": ["s1"]}
