"""Domain service entrypoints for Telegram-free sticker-pack behavior.

This package re-exports the service used to resolve and mutate effective sticker packs without
depending on Telegram or persistence details.
"""

from .sticker_pack_service import StickerPackService

__all__ = ["StickerPackService"]
