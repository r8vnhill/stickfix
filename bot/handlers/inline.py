""" "Stickfix" (c) by Ignacio Slater M.
"Stickfix" is licensed under a
Creative Commons Attribution 4.0 International License.

You should have received a copy of the license along with this
work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""

from pathlib import Path
from uuid import uuid4

from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultCachedSticker,
    InputTextMessageContent,
    ParseMode,
    Update,
)
from telegram.ext import CallbackContext, ChosenInlineResultHandler, Dispatcher, InlineQueryHandler

from bot.application.ports import UserRepository
from bot.application.requests import ClearInlineCacheCommand, InlineQueryRequest
from bot.application.results import InlineQueryResult
from bot.application.use_cases.clear_inline_cache import ClearInlineCache
from bot.application.use_cases.resolve_inline_query import ResolveInlineQuery
from bot.domain.services.sticker_pack_service import StickerPackService
from bot.handlers.common import HELP_PATH, StickfixHandler, optional_caller_id
from bot.infrastructure.help.file_help_content_provider import FileHelpContentProvider
from bot.utils.errors import unexpected_error
from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)

#: Maximum sticker results returned per inline-query page (Telegram allows 50).
_INLINE_PAGE_LIMIT = 49


class InlineHandler(StickfixHandler):
    """Wire Telegram inline queries and chosen-result callbacks to their use cases.

    ``__inline_get`` answers an inline query with a page of cached-sticker results
    (plus an optional help article); ``__on_result`` clears the caller's inline
    cache once they pick a result. Both keep only Telegram parsing/formatting -- the
    ``ResolveInlineQuery`` and ``ClearInlineCache`` use cases own the logic. The
    ``*_use_case`` constructor parameters exist so tests can inject fakes; when
    omitted, ``_build_default_*`` assembles the real use case from infrastructure.
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        users: UserRepository,
        resolve_inline_query: ResolveInlineQuery | None = None,
        clear_inline_cache: ClearInlineCache | None = None,
    ) -> None:
        super().__init__(dispatcher, users)
        self._resolve_inline_query = (
            resolve_inline_query or self._build_default_resolve_inline_query(users)
        )
        self._clear_inline_cache = clear_inline_cache or self._build_default_clear_inline_cache(
            users
        )
        self._dispatcher.add_handler(InlineQueryHandler(self.__inline_get))
        self._dispatcher.add_handler(ChosenInlineResultHandler(self.__on_result))

    @staticmethod
    def _build_default_resolve_inline_query(
        users: UserRepository,
    ) -> ResolveInlineQuery:
        """Build the default ResolveInlineQuery use case from infrastructure."""
        help_provider = FileHelpContentProvider(Path(HELP_PATH))
        pack_service = StickerPackService()
        return ResolveInlineQuery(
            users=users,
            help_content=help_provider,
            stickers=pack_service,
        )

    @staticmethod
    def _build_default_clear_inline_cache(
        users: UserRepository,
    ) -> ClearInlineCache:
        """Build the default ClearInlineCache use case from infrastructure."""
        pack_service = StickerPackService()
        return ClearInlineCache(
            users=users,
            stickers=pack_service,
        )

    def __inline_get(
        self,
        update: Update,
        context: CallbackContext,
    ) -> None:
        """Get stickers matching inline query and answer with paginated results."""
        try:
            inline_query = update.inline_query
            request = InlineQueryRequest(
                user_id=optional_caller_id(update),
                query_text=inline_query.query,
                offset=int(inline_query.offset or 0),
                limit=_INLINE_PAGE_LIMIT,
            )
            result = self._resolve_inline_query(request)
            context.bot.answer_inline_query(
                inline_query.id,
                self._to_telegram_results(result),
                cache_time=1,
                is_personal=True,
                next_offset=str(result.next_offset),
            )
        except Exception as e:
            unexpected_error(e, logger)
            raise e

    def _to_telegram_results(self, result: InlineQueryResult) -> list:
        """Convert an application result into Telegram inline-result objects."""
        telegram_results: list = []
        if result.show_default_help and result.help_text is not None:
            telegram_results.append(self._build_help_article(result))
        telegram_results.extend(
            InlineQueryResultCachedSticker(id=str(uuid4()), sticker_file_id=sticker_id)
            for sticker_id in result.sticker_ids
        )
        return telegram_results

    def __on_result(
        self,
        update: Update,
        context: CallbackContext,  # noqa: ARG002
    ) -> None:
        """Clear cached stickers after a chosen inline result."""
        try:
            chosen_result = update.chosen_inline_result
            self._clear_inline_cache(
                ClearInlineCacheCommand(
                    user_id=optional_caller_id(update),
                    query_text=chosen_result.query,
                )
            )
            logger.info(f"Answered inline query for {chosen_result.query}")
        except Exception as e:
            unexpected_error(e, logger)

    @staticmethod
    def _build_help_article(result: InlineQueryResult) -> InlineQueryResultArticle:
        """Convert application result into a Telegram help article."""
        first_tag = result.default_tags[0] if result.default_tags else "help"
        return InlineQueryResultArticle(
            id=str(uuid4()),
            title="Click me for help",
            description=f"Try calling me inline like `@stickfixbot {first_tag}`",
            input_message_content=InputTextMessageContent(
                result.help_text,
                parse_mode=ParseMode.MARKDOWN,
            ),
        )
