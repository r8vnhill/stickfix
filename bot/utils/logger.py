from __future__ import annotations

import logging
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoggerConfig:
    console_level: int = logging.DEBUG
    file_level: int = logging.INFO
    level: int = logging.DEBUG
    log_path: Path = Path("logs") / "stickfix.log"
    max_bytes: int = 50_000
    backup_count: int = 2
    console_format: str = "%(levelname)s:%(name)s:%(message)s"
    file_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class StickfixLogger:
    """Simple facade that ensures bot logging is configured once per logger name."""

    def __init__(self, context: str, *, config: LoggerConfig | None = None):
        self.__config = config or LoggerConfig()
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

    def __configure_logger(self, context: str) -> logging.Logger:
        logger = logging.getLogger(context)
        logger.setLevel(self.__config.level)
        self.__ensure_handlers(logger)
        return logger

    def __ensure_handlers(self, logger: logging.Logger) -> None:
        if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
            console = logging.StreamHandler()
            console.setLevel(self.__config.console_level)
            console.setFormatter(logging.Formatter(self.__config.console_format))
            logger.addHandler(console)

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
