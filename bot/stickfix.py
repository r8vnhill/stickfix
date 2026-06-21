"""Stickfix bot bootstrap: builds the Telegram updater, wires handlers, and runs
the bot through long polling (never PTB's Tornado webhook server)."""

from typing import Any, Final, cast

from telegram.ext import CallbackContext, Dispatcher, JobQueue, Updater

from bot.database.storage import StickfixDB
from bot.handlers.inline import InlineHandler
from bot.handlers.stickers import StickerHandler
from bot.handlers.utility import HelperHandler, UserHandler
from bot.utils.logger import StickfixLogger

USERS_DB: Final[str] = "users"

DataDict = dict[str, Any]
CallbackCtx = CallbackContext[DataDict, DataDict, DataDict]


def start_polling_service(
    updater: "Updater[CallbackCtx, DataDict, DataDict, DataDict]",
    logger: StickfixLogger,
) -> None:
    """Starts the bot's update transport in polling mode.

    Stickfix intentionally runs through Telegram long polling and never starts
    PTB's Tornado-based webhook server. This keeps the bot off any HTTP listening
    port, so the vulnerable ``multipart/form-data`` parser in Tornado (see
    CVE-2026-31958) is never reachable through Stickfix.
    """
    logger.info("Starting bot polling service.")
    updater.start_polling()  # pyright: ignore[reportUnknownMemberType]


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
        self.__logger = StickfixLogger(__name__)
        self.__start_updater(token)
        self.__dispatcher = cast(
            "Dispatcher[CallbackCtx, DataDict, DataDict, DataDict]",
            self.__updater.dispatcher,  # pyright: ignore[reportUnknownMemberType]
        )
        self.__user_db = StickfixDB(USERS_DB)
        self.__setup_handlers()
        job_queue = cast(JobQueue, self.__updater.job_queue)  # pyright: ignore[reportUnknownMemberType]
        job_queue.run_repeating(  # pyright: ignore[reportUnknownMemberType]
            self.__save_db, interval=5 * 60, first=0
        )

    def run(self) -> None:
        """Runs the bot."""
        start_polling_service(self.__updater, self.__logger)

    def __start_updater(self, token: str) -> None:
        """Starts the bot's updater with the given token."""
        self.__logger.info("Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    def __save_db(self, _context: CallbackCtx) -> None:
        self.__user_db.save()

    def __setup_handlers(self) -> None:
        HelperHandler(self.__dispatcher, self.__user_db)
        UserHandler(self.__dispatcher, self.__user_db)
        StickerHandler(self.__dispatcher, self.__user_db)
        InlineHandler(self.__dispatcher, self.__user_db)
