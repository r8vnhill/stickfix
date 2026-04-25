"""Persistence adapters implementing application repository ports.

This package provides concrete implementations of application ports (e.g.,
UserRepository) that wrap the legacy YAML-backed storage backends. Adapters
translate between domain types and storage format, allowing use cases to work
with domain objects rather than raw YAML/storage details.

Handlers instantiate and inject adapters into use cases. Tests can substitute
in-memory implementations for testing without filesystem/YAML dependencies.
"""

from .stickfix_user_repository import StickfixUserRepository

__all__ = ["StickfixUserRepository"]
