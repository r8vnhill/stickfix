"""Stickfix bot bootstrap: builds the Telegram updater, wires handlers, and runs
the bot through long polling (never PTB's Tornado webhook server)."""

import os
from typing import Any, cast

from telegram.ext import CallbackContext, Dispatcher, Updater

from bot.application.ports import UserRepository
from bot.config import DATABASE_URL_ENVVAR
from bot.handlers.inline import InlineHandler
from bot.handlers.stickers import StickerHandler
from bot.handlers.utility import HelperHandler, UserHandler
from bot.infrastructure.persistence.postgres import (
    PostgresUserRepository,
    create_engine_and_session_factory,
)
from bot.utils.logger import StickfixLogger

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
    """Composition root and public facade for @stickfixbot.

    Constructing a ``Stickfix`` builds the PTB ``Updater``/``Dispatcher``, resolves a
    :class:`UserRepository`, and registers every command/inline handler against it.
    ``Stickfix(token).run()`` is the stable entry point kept working across the
    persistence rewrite; ``bot.__main__`` calls it with values from
    :func:`bot.config.load_config`.

    Args (``__init__``):
        token: Telegram bot token passed straight to ``Updater``.
        users: Repository to inject. Tests pass a fake here; production leaves it
            ``None`` so ``__build_repository`` constructs a ``PostgresUserRepository``.
        database_url: SQLAlchemy URL used only when ``users`` is ``None``; falls back
            to ``STICKFIX_DATABASE_URL`` and raises ``RuntimeError`` if neither is set.
    """

    __updater: Updater[CallbackCtx, DataDict, DataDict, DataDict]
    __dispatcher: Dispatcher[CallbackCtx, DataDict, DataDict, DataDict]
    __logger: StickfixLogger
    __users: UserRepository

    def __init__(
        self,
        token: str,
        users: UserRepository | None = None,
        database_url: str | None = None,
    ):
        self.__logger = StickfixLogger(__name__)
        self.__start_updater(token)
        self.__dispatcher = cast(
            "Dispatcher[CallbackCtx, DataDict, DataDict, DataDict]",
            self.__updater.dispatcher,  # pyright: ignore[reportUnknownMemberType]
        )
        self.__users = users or self.__build_repository(database_url)
        self.__setup_handlers()

    def run(self) -> None:
        """Runs the bot."""
        start_polling_service(self.__updater, self.__logger)

    def __start_updater(self, token: str) -> None:
        """Starts the bot's updater with the given token."""
        self.__logger.info("Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    @staticmethod
    def __build_repository(database_url: str | None) -> UserRepository:
        resolved_url = database_url or os.environ.get(DATABASE_URL_ENVVAR, "").strip()
        if not resolved_url:
            raise RuntimeError(f"{DATABASE_URL_ENVVAR} must be configured")
        _, session_factory = create_engine_and_session_factory(resolved_url)
        return PostgresUserRepository(session_factory)

    def __setup_handlers(self) -> None:
        HelperHandler(self.__dispatcher, self.__users)
        UserHandler(self.__dispatcher, self.__users)
        StickerHandler(self.__dispatcher, self.__users)
        InlineHandler(self.__dispatcher, self.__users)
