"""SQLAlchemy engine and session construction."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_and_session_factory(
    database_url: str,
) -> tuple[Engine, Callable[[], Session]]:
    """Create a pre-ping engine and a non-expiring session factory."""
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, factory
