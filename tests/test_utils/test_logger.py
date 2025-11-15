"""
BDD/property tests for the stickfix logger configuration.
"""

from __future__ import annotations

import logging
import string
import uuid
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, List

import pytest
from hypothesis import given as hypothesis_given
from hypothesis import strategies as st
from pytest_bdd import given as bdd_given
from pytest_bdd import parsers, scenarios
from pytest_bdd import then as bdd_then
from pytest_bdd import when as bdd_when

from bot.utils.logger import LoggerConfig, StickfixLogger

FEATURE_FILE: Path = Path(__file__).resolve().parents[1] / "features" / "logger.feature"
scenarios(str(FEATURE_FILE))


def _reset_logger(name: str) -> None:
    """Reset a logger instance to a clean state.

    Tests that construct Logger instances add handlers to the global `logging` registry. To avoid
    handler leakage between tests we remove any handlers attached to the named logger and close
    them. We also reset the logger level to `NOTSET` so subsequent tests start from a predictable
    state.

    This helper is safe to call multiple times and is used in teardown paths when tests create
    temporary log files and handlers.

    Args:
        name (str): the logger name to reset
    """
    logger = logging.getLogger(name)
    # Iterate over a copy since removing handlers mutates the list
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        # Best practice: close handlers to release file descriptors
        handler.close()
    # Reset level so that the logger inherits behavior from the root logger
    logger.setLevel(logging.NOTSET)


@dataclass
class LoggerState:
    tmp_path: Path
    name: str | None = None
    config: LoggerConfig | None = None
    instances: List[StickfixLogger] = field(default_factory=list)


@pytest.fixture
def logger_state(tmp_path: Path):
    """Fixture that provides a mutable container to hold test state.

    The fixture yields a `LoggerState` object that tests populate with the
    logger name, config and any created `StickfixLogger` instances. On
    teardown we call `_reset_logger` (when a name was set) to ensure
    handlers are removed and temporary files can be cleaned up without
    clashes on Windows or other platforms.
    """
    state = LoggerState(tmp_path=tmp_path)
    yield state
    # Teardown: ensure no handlers remain attached to the logger name
    if state.name:
        _reset_logger(state.name)


@bdd_given(parsers.parse('a logger context "{context}"'))
def a_logger_context(logger_state: LoggerState, context: str) -> None:
    # Create a unique log file path under the fixture's temporary directory
    # Use the context string to form a predictable file name for assertions
    log_file = logger_state.tmp_path / f"{context.replace('.', '_')}.log"
    logger_state.name = context
    # Provide a LoggerConfig pointing at the temporary log file
    logger_state.config = LoggerConfig(log_path=log_file)


@bdd_when(parsers.parse("I instantiate the logger {count:d} times"))
def instantiate_logger(logger_state: LoggerState, count: int) -> None:
    assert isinstance(logger_state.name, str)
    assert isinstance(logger_state.config, LoggerConfig)
    for _ in range(count):
        # Create StickfixLogger instances; the implementation should ensure
        # multiple instantiations don't add duplicate handlers.
        instance = StickfixLogger(logger_state.name, config=logger_state.config)
        logger_state.instances.append(instance)


def _get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _count_handlers(logger: logging.Logger, predicate: Callable[[logging.Handler], bool]) -> int:
    return sum(1 for handler in logger.handlers if predicate(handler))


@bdd_then("the logger has exactly 1 console handler")
def assert_console_handler(logger_state: LoggerState) -> None:
    assert isinstance(logger_state.name, str)
    logger = _get_logger(logger_state.name)
    assert _count_handlers(logger, lambda h: type(h) is logging.StreamHandler) == 1


@bdd_then("the logger has exactly 1 rotating file handler")
def assert_file_handler(logger_state: LoggerState) -> None:
    assert isinstance(logger_state.name, str)
    logger = _get_logger(logger_state.name)
    assert _count_handlers(logger, lambda h: isinstance(h, RotatingFileHandler)) == 1


@bdd_then("the log file is created")
def assert_log_file_created(logger_state: LoggerState) -> None:
    assert isinstance(logger_state.config, LoggerConfig)
    assert logger_state.config.log_path.exists()


@hypothesis_given(
    segments=st.lists(
        st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=8),
        min_size=2,
        max_size=4,
    )
)
def test_logger_creates_nested_paths(segments: List[str]) -> None:
    with TemporaryDirectory() as tmp_dir:
        base = Path(tmp_dir)
        directory_segments = segments[:-1]
        filename = f"{segments[-1]}.log"
        log_path = base.joinpath(*directory_segments, filename)
        config = LoggerConfig(log_path=log_path)
        logger_name = f"stickfix.property.{uuid.uuid4().hex}"
        try:
            StickfixLogger(logger_name, config=config)
            assert log_path.exists()
            assert log_path.parent.exists()
        finally:
            _reset_logger(logger_name)
