"""Typed identifiers shared by domain objects and application contracts.

``UserId`` remains an ``int`` at runtime, but gives repository and use-case
signatures a name for the Telegram user identity they exchange. Keeping this
alias here avoids coupling the domain package to a transport or database type.
"""

from typing import NewType

UserId = NewType("UserId", int)

__all__ = ["UserId"]
