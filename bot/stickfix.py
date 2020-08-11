""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""

from telegram.ext import Dispatcher, JobQueue, \
    Updater

from bot.database.storage import StickfixDB
from bot.handlers.stickers import StickerHandler
from bot.handlers.utility import HelperHandler, UserHandler
from bot.utils.logger import StickfixLogger

SF_PUBLIC = "SF-PUBLIC"
USERS_DB = "users"


class Stickfix:
    """ Base class for @stickfixbot.
        This class implements functions to help manage and store stickers in telegram using chat
        commands and inline queries.
    """
    __updater: Updater
    __dispatcher: Dispatcher
    __logger: StickfixLogger
    __user_db: StickfixDB

    def __init__(self, token: str):
        """ Initializes the bot.

        :param token:
            the bot's telegram token
        """
        job_queue: JobQueue
        self.__logger = StickfixLogger(__name__)
        self.__start_updater(token)
        self.__dispatcher = self.__updater.dispatcher
        self.__user_db = StickfixDB(USERS_DB)
        self.__setup_handlers()
        job_queue = self.__updater.job_queue
        job_queue.run_repeating(self.__user_db.save, interval=5 * 60)

    def run(self) -> None:
        """ Runs the bot.   """
        self.__logger.info("Starting bot polling service.")
        self.__updater.start_polling()

    def __start_updater(self, token: str) -> None:
        """ Starts the bot's updater with the given token.  """
        self.__logger.info(f"Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    def __setup_handlers(self):
        HelperHandler(self.__dispatcher, self.__user_db)
        UserHandler(self.__dispatcher, self.__user_db)
        StickerHandler(self.__dispatcher, self.__user_db)
