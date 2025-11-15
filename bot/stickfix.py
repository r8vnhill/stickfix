from typing import Any, Dict

from telegram.ext import CallbackContext, Dispatcher, JobQueue, Updater

from bot.database.storage import StickfixDB
from bot.handlers.inline import InlineHandler
from bot.handlers.stickers import StickerHandler
from bot.handlers.utility import HelperHandler, UserHandler
from bot.utils.logger import StickfixLogger

USERS_DB = "users"

DataDict = Dict[str, Any]
CallbackCtx = CallbackContext[DataDict, DataDict, DataDict]


class Stickfix:
    """Base class for @stickfixbot.
    This class implements functions to help manage and store stickers in telegram using chat
    commands and inline queries.
    """

    __updater: Updater[CallbackCtx, DataDict, DataDict, DataDict]
    __dispatcher: Dispatcher[CallbackCtx, DataDict, DataDict, DataDict]
    __logger: StickfixLogger
    __user_db: StickfixDB

    def __init__(self, token: str):
        """Initializes the bot.

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
        job_queue.run_repeating(self.__save_db, interval=5 * 60, first=0)

    def run(self) -> None:
        """Runs the bot."""
        self.__logger.info("Starting bot polling service.")
        self.__updater.start_polling()

    def __start_updater(self, token: str) -> None:
        """Starts the bot's updater with the given token."""
        self.__logger.info(f"Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    # noinspection PyUnusedLocal
    def __save_db(self, context: CallbackCtx):
        self.__user_db.save()

    def __setup_handlers(self):
        HelperHandler(self.__dispatcher, self.__user_db)
        UserHandler(self.__dispatcher, self.__user_db)
        StickerHandler(self.__dispatcher, self.__user_db)
        InlineHandler(self.__dispatcher, self.__user_db)
