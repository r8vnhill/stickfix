"""Alembic environment configured from STICKFIX_DATABASE_URL."""

# Alembic exposes this module as a runtime proxy while executing an env file;
# Pylint cannot discover that proxy's members through static analysis.
# pylint: disable=no-member

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context  # pylint: disable=no-name-in-module
from bot.infrastructure.persistence.postgres.models import Base

config = context.config
if config.config_file_name is not None:
  fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
  """Return the configured database URL or fail before running migrations."""
  value = os.environ.get("STICKFIX_DATABASE_URL", "").strip()
  if not value:
    raise RuntimeError("STICKFIX_DATABASE_URL must be configured for Alembic")
  return value


def run_migrations_offline() -> None:
  """Run migrations without opening a database connection."""
  context.configure(
    url=database_url(),
    target_metadata=target_metadata,
    literal_binds=True,
    dialect_opts={"paramstyle": "named"},
  )
  with context.begin_transaction():
    context.run_migrations()


def run_migrations_online() -> None:
  """Run migrations against the configured database connection."""
  configuration = config.get_section(config.config_ini_section, {})
  configuration["sqlalchemy.url"] = database_url()
  connectable = engine_from_config(
    configuration,
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
  )
  with connectable.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
      context.run_migrations()


if context.is_offline_mode():
  run_migrations_offline()
else:
  run_migrations_online()
