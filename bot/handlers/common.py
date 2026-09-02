""" "Stickfix" (c) by Ignacio Slater M.
"Stickfix" is licensed under a
Creative Commons Attribution 4.0 International License.

You should have received a copy of the license along with this
work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""

from telegram import Update
from telegram.ext import Dispatcher

from bot.domain.identifiers import UserId

HELP_PATH = "bot/utils/HELP.md"


def caller_id(update: Update) -> UserId:
    """Return the update's effective user as a domain ``UserId``.

    Every command handler needs the numeric Telegram id in this exact form before
    building an application request; centralising the ``int`` cast keeps that
    conversion in one place. Assumes ``effective_user`` is present, which Telegram
    guarantees for command messages.
    """
    return UserId(int(update.effective_user.id))


def optional_caller_id(update: Update) -> UserId | None:
    """Like :func:`caller_id` but tolerates anonymous updates (some inline traffic)."""
    user = update.effective_user
    return UserId(int(user.id)) if user is not None else None


class StickfixHandler:
    """Base for command/inline handlers: holds the Telegram dispatcher.

    Subclasses register their Telegram handlers in ``__init__`` and translate each
    callback into an application use-case call. Shared, Telegram-free helpers that
    more than one handler needs live here.
    """

    _dispatcher: Dispatcher

    def __init__(self, dispatcher: Dispatcher):
        self._dispatcher = dispatcher
