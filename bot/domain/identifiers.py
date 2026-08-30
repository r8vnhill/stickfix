"""Semantic identifiers used by the domain and application contracts."""

from typing import NewType

UserId = NewType("UserId", int)

__all__ = ["UserId"]
