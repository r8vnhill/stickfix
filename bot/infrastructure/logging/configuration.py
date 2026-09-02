"""Standard-library logging configuration for the runtime composition root.

The module keeps file/console handler construction in infrastructure. Application,
domain, and Telegram adapters only request named standard-library loggers. Set
``STICKFIX_LOG_PATH`` to override the rotating file location or set
``STICKFIX_DISABLE_FILE_LOGGING=1`` for tests and environments without a writable
log directory.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = Path("logs") / "stickfix.log"
LOG_PATH_ENVVAR = "STICKFIX_LOG_PATH"
DISABLE_FILE_LOGGING_ENVVAR = "STICKFIX_DISABLE_FILE_LOGGING"


@dataclass(frozen=True)
class LoggerConfig:
    """Handler levels, formats, and rotation settings for one logger context."""

    console_level: int = logging.DEBUG
    file_level: int = logging.INFO
    level: int = logging.DEBUG
    log_path: Path | None = DEFAULT_LOG_PATH
    max_bytes: int = 50_000
    backup_count: int = 2
    console_format: str = "%(levelname)s:%(name)s:%(message)s"
    file_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class StickfixLogger:
    """Compatibility facade for the historical logger API.

    New code should use ``logging.getLogger(__name__)`` and let the composition
    root call :func:`configure_logging` once. The facade remains available to
    existing callers while delegating every operation to ``logging.Logger``.
    """

    def __init__(self, context: str, *, config: LoggerConfig | None = None):
        self.__config = config or self.__default_config()
        self.__logger = self.__configure_logger(context)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.exception(msg, *args, **kwargs)

    def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.log(level, msg, *args, **kwargs)

    @property
    def logger(self) -> logging.Logger:
        """Expose the configured logger for advanced integrations or tests."""
        return self.__logger

    @staticmethod
    def __default_config() -> LoggerConfig:
        if os.environ.get(DISABLE_FILE_LOGGING_ENVVAR, "").strip() == "1":
            return LoggerConfig(log_path=None)
        log_path_value = os.environ.get(LOG_PATH_ENVVAR, "").strip()
        if log_path_value:
            return LoggerConfig(log_path=Path(log_path_value))
        return LoggerConfig()

    def __configure_logger(self, context: str) -> logging.Logger:
        logger = logging.getLogger(context)
        logger.setLevel(self.__config.level)
        self.__ensure_handlers(logger)
        return logger

    def __ensure_handlers(self, logger: logging.Logger) -> None:
        if not any(type(handler) is logging.StreamHandler for handler in logger.handlers):
            console = logging.StreamHandler()
            console.setLevel(self.__config.console_level)
            console.setFormatter(logging.Formatter(self.__config.console_format))
            logger.addHandler(console)
        if self.__config.log_path is None:
            return
        if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
            self.__config.log_path.parent.mkdir(parents=True, exist_ok=True)
            file_logger = RotatingFileHandler(
                filename=self.__config.log_path,
                encoding="utf-8",
                maxBytes=self.__config.max_bytes,
                backupCount=self.__config.backup_count,
            )
            file_logger.setLevel(self.__config.file_level)
            file_logger.setFormatter(logging.Formatter(self.__config.file_format))
            logger.addHandler(file_logger)


def configure_logging(
    context: str = "bot", *, config: LoggerConfig | None = None
) -> logging.Logger:
    """Configure handlers for ``context`` and return its standard logger.

    Repeated calls are idempotent with respect to the console and rotating-file
    handler types, which matters when tests construct multiple bot instances.
    """
    return StickfixLogger(context, config=config).logger
