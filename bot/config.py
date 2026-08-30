"""Environment-driven configuration for the Stickfix composition root.

``load_config`` is the single place that reads process environment / CLI overrides
into an immutable :class:`StickfixConfig`. Nothing else in the codebase should call
``os.environ`` for these keys. ``bot.__main__`` and ``bot.stickfix.Stickfix`` consume
the resulting dataclass; tests pass an explicit ``environ`` mapping instead of
touching the real environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_ENV = "dev"
ENV_ENVVAR = "STICKFIX_ENV"
GENERIC_TOKEN_ENVVAR = "STICKFIX_TOKEN"  # noqa: S105
TOKEN_FILE_ENVVAR = "STICKFIX_TOKEN_FILE"  # noqa: S105
LOG_PATH_ENVVAR = "STICKFIX_LOG_PATH"
DATABASE_URL_ENVVAR = "STICKFIX_DATABASE_URL"
TOKEN_BY_ENV: dict[str, str] = {
    "dev": "STICKFIX_TOKEN_DEV",
    "prod": "STICKFIX_TOKEN_PROD",
}


class ConfigError(ValueError):
    """Raised when Stickfix configuration cannot be resolved."""


@dataclass(frozen=True)
class StickfixConfig:
    """Fully resolved runtime configuration.

    Attributes:
        env: Normalised environment name (``"dev"`` / ``"prod"``), lower-cased.
        token: Telegram bot token; always non-empty (resolution raises otherwise).
        log_path: Optional override for the log file location.
        database_url: SQLAlchemy URL for PostgreSQL, or ``None`` when unset (the bot
            then falls back to ``STICKFIX_DATABASE_URL`` at repository build time).
    """

    env: str
    token: str
    log_path: Path | None = None
    database_url: str | None = None


def load_config(
    *,
    token: str | None = None,
    token_file: str | os.PathLike[str] | None = None,
    env: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> StickfixConfig:
    """Load Stickfix configuration from CLI overrides and environment variables.

    Resolution order for token:
    1. Explicit token argument (CLI `--token`)
    2. `STICKFIX_TOKEN`
    3. Env-specific token (`STICKFIX_TOKEN_DEV`/`STICKFIX_TOKEN_PROD`)
    4. Token file (`STICKFIX_TOKEN_FILE` or `--token-file`)
    """
    env_vars = dict(os.environ if environ is None else environ)
    resolved_env = _resolve_env(env, env_vars)
    resolved_token = _resolve_token(env_vars, resolved_env, token, token_file)
    log_path_value = env_vars.get(LOG_PATH_ENVVAR)
    log_path = Path(log_path_value) if log_path_value else None
    database_url = env_vars.get(DATABASE_URL_ENVVAR, "").strip() or None
    return StickfixConfig(
        env=resolved_env,
        token=resolved_token,
        log_path=log_path,
        database_url=database_url,
    )


def _resolve_env(env: str | None, env_vars: Mapping[str, str]) -> str:
    candidate = env or env_vars.get(ENV_ENVVAR, DEFAULT_ENV)
    return (candidate or DEFAULT_ENV).strip().lower() or DEFAULT_ENV


def _resolve_token(
    env_vars: Mapping[str, str],
    env: str,
    token_override: str | None,
    token_file_override: str | os.PathLike[str] | None,
) -> str:
    """Return the first token configured, following the priority in :func:`load_config`."""
    env_token_var = TOKEN_BY_ENV.get(env)
    inline_candidates = (
        token_override,
        env_vars.get(GENERIC_TOKEN_ENVVAR),
        env_vars.get(env_token_var) if env_token_var else None,
    )
    for candidate in inline_candidates:
        if candidate and candidate.strip():
            return candidate.strip()
    return _token_from_file(token_file_override or env_vars.get(TOKEN_FILE_ENVVAR))


def _token_from_file(path: str | os.PathLike[str] | None) -> str:
    if not path:
        raise ConfigError(
            "Stickfix token missing. Provide --token or set STICKFIX_TOKEN, "
            "STICKFIX_TOKEN_DEV/PROD, or STICKFIX_TOKEN_FILE."
        )
    token = Path(path).read_text(encoding="utf-8").strip()
    if not token:
        raise ConfigError(f"Token file '{path}' is empty")
    return token
