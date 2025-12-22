from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_ENV = "dev"
ENV_ENVVAR = "STICKFIX_ENV"
GENERIC_TOKEN_ENVVAR = "STICKFIX_TOKEN"
TOKEN_FILE_ENVVAR = "STICKFIX_TOKEN_FILE"
LOG_PATH_ENVVAR = "STICKFIX_LOG_PATH"
TOKEN_BY_ENV: dict[str, str] = {
    "dev": "STICKFIX_TOKEN_DEV",
    "prod": "STICKFIX_TOKEN_PROD",
}


class ConfigError(ValueError):
    """Raised when Stickfix configuration cannot be resolved."""


@dataclass(frozen=True)
class StickfixConfig:
    env: str
    token: str
    log_path: Path | None = None


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
    return StickfixConfig(env=resolved_env, token=resolved_token, log_path=log_path)


def _resolve_env(env: str | None, env_vars: Mapping[str, str]) -> str:
    candidate = env or env_vars.get(ENV_ENVVAR, DEFAULT_ENV)
    return (candidate or DEFAULT_ENV).strip().lower() or DEFAULT_ENV


def _resolve_token(
    env_vars: Mapping[str, str],
    env: str,
    token_override: str | None,
    token_file_override: str | os.PathLike[str] | None,
) -> str:
    if token_override:
        return token_override

    generic = env_vars.get(GENERIC_TOKEN_ENVVAR, "").strip()
    if generic:
        return generic

    env_token_var = TOKEN_BY_ENV.get(env)
    if env_token_var:
        env_specific = env_vars.get(env_token_var, "").strip()
        if env_specific:
            return env_specific

    token_file_path = token_file_override or env_vars.get(TOKEN_FILE_ENVVAR)
    if token_file_path:
        token_from_file = Path(token_file_path).read_text(encoding="utf-8").strip()
        if token_from_file:
            return token_from_file
        raise ConfigError(f"Token file '{token_file_path}' is empty")

    raise ConfigError(
        "Stickfix token missing. Provide --token or set STICKFIX_TOKEN, "
        "STICKFIX_TOKEN_DEV/PROD, or STICKFIX_TOKEN_FILE."
    )
