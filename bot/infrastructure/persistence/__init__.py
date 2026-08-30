"""Runtime persistence adapters implementing application repository ports.

PostgreSQL is the runtime implementation. The historical YAML adapter remains
in its own module for legacy tests and migration support, but is not imported
by the normal persistence package.
"""

from .postgres import PostgresUserRepository

__all__ = ["PostgresUserRepository"]
