""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
from telegram.ext import Dispatcher

from bot.database.storage import StickfixDB
from bot.database.users import StickfixUser
from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)


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
