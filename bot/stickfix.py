"""Stickfix bot bootstrap: builds the Telegram updater, wires handlers, and runs
the bot through long polling (never PTB's Tornado webhook server)."""

import logging
import os
from pathlib import Path
from typing import Any, cast

from telegram.ext import CallbackContext, Dispatcher, Updater

from bot.application.ports import PublicPackRepository, UserRepository
from bot.application.use_cases import (
    AddSticker,
    ClearInlineCache,
    DeleteSticker,
    DeleteUser,
    EnsureUser,
    GetHelp,
    GetStickers,
    ResolveInlineQuery,
    SetMode,
    SetShuffle,
)
from bot.config import DATABASE_URL_ENVVAR
from bot.domain.services import StickerPackService
from bot.handlers.common import HELP_PATH
from bot.handlers.inline import InlineHandler
from bot.handlers.stickers import StickerHandler
from bot.handlers.utility import HelperHandler, UserHandler
from bot.infrastructure.help import FileHelpContentProvider
from bot.infrastructure.logging import configure_logging
from bot.infrastructure.persistence.postgres import (
    PostgresUserRepository,
    create_engine_and_session_factory,
)

DataDict = dict[str, Any]
CallbackCtx = CallbackContext[DataDict, DataDict, DataDict]


def start_polling_service(
    updater: "Updater[CallbackCtx, DataDict, DataDict, DataDict]",
    logger: logging.Logger,
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
        public: Shared-pack repository to inject when ``users`` does not implement
            both application repository ports.
        database_url: SQLAlchemy URL used only when ``users`` is ``None``; falls back
            to ``STICKFIX_DATABASE_URL`` and raises ``RuntimeError`` if neither is set.
    """

    __updater: Updater[CallbackCtx, DataDict, DataDict, DataDict]
    __dispatcher: Dispatcher[CallbackCtx, DataDict, DataDict, DataDict]
    __logger: logging.Logger
    __users: UserRepository
    __public: PublicPackRepository

    def __init__(
        self,
        token: str,
        users: UserRepository | None = None,
        database_url: str | None = None,
        public: PublicPackRepository | None = None,
    ):
        self.__logger = configure_logging("bot")
        self.__start_updater(token)
        self.__dispatcher = cast(
            "Dispatcher[CallbackCtx, DataDict, DataDict, DataDict]",
            self.__updater.dispatcher,  # pyright: ignore[reportUnknownMemberType]
        )
        self.__users, self.__public = self.__resolve_repositories(users, public, database_url)
        self.__setup_handlers()

    def run(self) -> None:
        """Runs the bot."""
        start_polling_service(self.__updater, self.__logger)

    def __start_updater(self, token: str) -> None:
        """Starts the bot's updater with the given token."""
        self.__logger.info("Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    @staticmethod
    def __build_repository(
        database_url: str | None,
    ) -> tuple[UserRepository, PublicPackRepository]:
        """Construct the Postgres repository from an explicit URL or the env var.

        ``PostgresUserRepository`` implements both ports, so the same instance is
        returned for the user and public-pack roles. Raises ``RuntimeError`` when
        neither ``database_url`` nor ``STICKFIX_DATABASE_URL`` is set.
        """
        resolved_url = database_url or os.environ.get(DATABASE_URL_ENVVAR, "").strip()
        if not resolved_url:
            raise RuntimeError(f"{DATABASE_URL_ENVVAR} must be configured")
        _, session_factory = create_engine_and_session_factory(resolved_url)
        repository = PostgresUserRepository(session_factory)
        return repository, repository

    @staticmethod
    def __resolve_repositories(
        users: UserRepository | None,
        public: PublicPackRepository | None,
        database_url: str | None,
    ) -> tuple[UserRepository, PublicPackRepository]:
        """Pick the (user, public-pack) repository pair to wire handlers with.

        Production passes nothing and gets a Postgres pair. Tests inject a ``users``
        fake; if it also satisfies :class:`PublicPackRepository` it doubles as the
        public port, otherwise an explicit ``public`` fake is required (``TypeError``
        if missing) so a use case can never silently lose the public pack.
        """
        if users is None:
            return Stickfix.__build_repository(database_url)
        if public is None:
            if not isinstance(users, PublicPackRepository):
                raise TypeError("public repository must be provided when users lacks that port")
            public = users
        return users, public

    def __setup_handlers(self) -> None:
        """Build each use case once and inject it into its Telegram adapter."""
        help_content = FileHelpContentProvider(Path(HELP_PATH))
        stickers = StickerPackService()
        ensure_user = EnsureUser(self.__users)
        get_help = GetHelp(help_content)
        add_sticker = AddSticker(self.__users, self.__public, stickers)
        get_stickers = GetStickers(self.__users, self.__public, stickers)
        delete_sticker = DeleteSticker(self.__users, self.__public, stickers)
        resolve_inline_query = ResolveInlineQuery(
            self.__users, help_content, self.__public, stickers
        )
        clear_inline_cache = ClearInlineCache(self.__users, self.__public, stickers)
        HelperHandler(self.__dispatcher, ensure_user, get_help)
        UserHandler(
            self.__dispatcher,
            SetMode(self.__users),
            SetShuffle(self.__users),
            DeleteUser(self.__users),
        )
        StickerHandler(self.__dispatcher, add_sticker, get_stickers, delete_sticker)
        InlineHandler(self.__dispatcher, resolve_inline_query, clear_inline_cache)
