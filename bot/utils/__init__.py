# SPDX-License-Identifier: BSD-2-Clause

"""Legacy Telegram-side helpers shared by the ``bot.handlers`` adapters.

``errors`` holds the adapter's own exception types, ``messages`` the command names and the
replied-sticker checks, and ``logger`` a compatibility facade over ``bot.infrastructure.logging``.
Milestone 4.5 splits these by adapter responsibility and retires them once nothing imports them;
add new Telegram helpers to ``stickfix_telegram`` instead of here.

``ALL`` is historical and is not ``__all__``: it does not affect ``from bot.utils import *``.
"""

ALL = ["logger", "messages", "errors"]
