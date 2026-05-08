"""Stable public facade for application-layer use cases.

Handlers and tests import use cases from this module instead of from per-use-case files. Keeping
imports centralized here makes call sites stable while the internal package evolves.

## Contract:

- exports only Telegram-free callable use-case classes
- does not import Telegram modules (validated by the application seam tests)
- treats ``__all__`` as the supported import surface for adapters and tests
"""

from .add_sticker import AddSticker
from .clear_inline_cache import ClearInlineCache
from .delete_sticker import DeleteSticker
from .get_stickers import GetStickers
from .resolve_inline_query import ResolveInlineQuery
from .set_mode import SetMode

__all__ = [
    "AddSticker",
    "ClearInlineCache",
    "DeleteSticker",
    "GetStickers",
    "ResolveInlineQuery",
    "SetMode",
]
