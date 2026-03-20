"""Stub imghdr module for Python 3.14+ where imghdr is removed."""

from __future__ import annotations

import os
from typing import BinaryIO


def what(
    file: str | bytes | os.PathLike[str] | BinaryIO | None = None,
    h: bytes | None = None,
) -> None:
    """Stub imghdr.what replacement for Python 3.14 where imghdr is removed."""
    del file, h
    return None
