""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import random
from typing import List

from telegram.ext import Dispatcher

from bot.database.storage import StickfixDB
from bot.database.users import SF_PUBLIC, StickfixUser
from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)

HELP_PATH = "bot/utils/HELP.md"


class StickfixHandler:
    _dispatcher: Dispatcher
    _user_db: StickfixDB

    def __init__(self, dispatcher: Dispatcher, user_db: StickfixDB):
        self._dispatcher = dispatcher
        self._user_db = user_db

    def _create_user(self, user_id):
        """ Creates and adds a user to the database.    """
        self._user_db[user_id] = StickfixUser(user_id)
        logger.info(f"Created user with id {user_id}")

    def _get_sticker_list(self, user: StickfixUser, tags: List[str]) -> List[str]:
        """ Returns the list of stickers associated with a tag and a user.  """
        stickers = []
        for tag in tags:
            logger.info(f"Getting stickers matching {tag}")
            match = self._user_db[user.id]
            if not user.private_mode:
                match = self._user_db[SF_PUBLIC].get_stickers(tag)
            match = match.union(user.get_stickers(tag))
            stickers.append(match)
            user.cache[tag] = list(match)
        stickers = list(set.intersection(*stickers))
        if user.shuffle:
            random.shuffle(stickers)
        return stickers
