from __future__ import annotations

import os
from pathlib import Path

import pytest

from bot.database.storage import StickfixDB

os.environ.setdefault("STICKFIX_DISABLE_FILE_LOGGING", "1")


@pytest.fixture
def store(tmp_path: Path) -> StickfixDB:
    return StickfixDB("users", data_dir=tmp_path)


@pytest.fixture
def store_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return (
        tmp_path / "users.yaml",
        tmp_path / "users.yaml_1.bak",
        tmp_path / "users.yaml_2.bak",
    )
