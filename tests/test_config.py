"""
Tests for env-driven Stickfix configuration resolution.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from bot.config import ConfigError, load_config


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Stickfix env vars do not leak between tests."""
    for key in [
        "STICKFIX_ENV",
        "STICKFIX_TOKEN",
        "STICKFIX_TOKEN_DEV",
        "STICKFIX_TOKEN_PROD",
        "STICKFIX_TOKEN_FILE",
        "STICKFIX_LOG_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_cli_token_takes_precedence(monkeypatch):
    monkeypatch.setenv("STICKFIX_TOKEN", "from-env")
    cfg = load_config(token="from-cli")
    assert cfg.token == "from-cli"
    assert cfg.env == "dev"


def test_generic_token_is_used_when_present(monkeypatch):
    monkeypatch.setenv("STICKFIX_TOKEN", "generic-token")
    cfg = load_config()
    assert cfg.token == "generic-token"
    assert cfg.env == "dev"


def test_env_specific_dev_is_used_by_default(monkeypatch):
    monkeypatch.setenv("STICKFIX_TOKEN_DEV", "dev-token")
    cfg = load_config()
    assert cfg.token == "dev-token"
    assert cfg.env == "dev"


def test_env_specific_prod_is_used_when_env_set(monkeypatch):
    monkeypatch.setenv("STICKFIX_ENV", "prod")
    monkeypatch.setenv("STICKFIX_TOKEN_PROD", "prod-token")
    cfg = load_config()
    assert cfg.token == "prod-token"
    assert cfg.env == "prod"


def test_token_file_is_used_as_last_resort(monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        token_path = Path(tmp_dir) / "token.txt"
        token_path.write_text("file-token\n", encoding="utf-8")
        monkeypatch.setenv("STICKFIX_TOKEN_FILE", str(token_path))
        cfg = load_config()
        assert cfg.token == "file-token"
        assert cfg.env == "dev"


def test_log_path_can_be_overridden(monkeypatch):
    monkeypatch.setenv("STICKFIX_TOKEN", "generic-token")
    monkeypatch.setenv("STICKFIX_LOG_PATH", "custom/logs/bot.log")
    cfg = load_config()
    assert cfg.log_path == Path("custom/logs/bot.log")


def test_error_is_raised_when_no_token_available():
    with pytest.raises(ConfigError):
        load_config()
