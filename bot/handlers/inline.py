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

from bot.application.requests import ClearInlineCacheCommand, InlineQueryRequest
from bot.application.use_cases.clear_inline_cache import ClearInlineCache
from bot.application.use_cases.resolve_inline_query import ResolveInlineQuery
from bot.database.storage import StickfixDB
from bot.domain.services.sticker_pack_service import StickerPackService
from bot.handlers.common import HELP_PATH, StickfixHandler
from bot.infrastructure.help.file_help_content_provider import FileHelpContentProvider
from bot.infrastructure.persistence.stickfix_user_repository import StickfixUserRepository
from bot.utils.errors import unexpected_error
from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)


class InlineHandler(StickfixHandler):
    def __init__(
        self,
        dispatcher: Dispatcher,
        user_db: StickfixDB,
        resolve_inline_query: ResolveInlineQuery | None = None,
        clear_inline_cache: ClearInlineCache | None = None,
    ) -> None:
        super().__init__(dispatcher, user_db)
        self._resolve_inline_query = (
            resolve_inline_query or self._build_default_resolve_inline_query(user_db)
        )
        self._clear_inline_cache = clear_inline_cache or self._build_default_clear_inline_cache(
            user_db
        )
        self._dispatcher.add_handler(InlineQueryHandler(self.__inline_get))
        self._dispatcher.add_handler(ChosenInlineResultHandler(self.__on_result))

    @staticmethod
    def _build_default_resolve_inline_query(
        user_db: StickfixDB,
    ) -> ResolveInlineQuery:
        """Build the default ResolveInlineQuery use case from infrastructure."""
        repository = StickfixUserRepository(user_db)
        help_provider = FileHelpContentProvider(Path(HELP_PATH))
        pack_service = StickerPackService()
        return ResolveInlineQuery(
            users=repository,
            help_content=help_provider,
            stickers=pack_service,
        )

    @staticmethod
    def _build_default_clear_inline_cache(
        user_db: StickfixDB,
    ) -> ClearInlineCache:
        """Build the default ClearInlineCache use case from infrastructure."""
        repository = StickfixUserRepository(user_db)
        pack_service = StickerPackService()
        return ClearInlineCache(
            users=repository,
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
            user = update.effective_user

            # Parse Telegram data safely
            user_id = str(user.id) if user is not None else None
            offset = int(0 if not inline_query.offset else inline_query.offset)

            # Build application request
            request = InlineQueryRequest(
                user_id=user_id,
                query_text=inline_query.query,
                offset=offset,
                limit=49,
            )

            # Delegate to application layer
            result = self._resolve_inline_query(request)

            # Convert application result to Telegram result objects
            telegram_results = []
            if result.show_default_help and result.help_text is not None:
                telegram_results.append(self._build_help_article(result))

            for sticker_id in result.sticker_ids:
                telegram_results.append(
                    InlineQueryResultCachedSticker(
                        id=str(uuid4()),
                        sticker_file_id=sticker_id,
                    )
                )

            # Answer the inline query
            context.bot.answer_inline_query(
                inline_query.id,
                telegram_results,
                cache_time=1,
                is_personal=True,
                next_offset=str(result.next_offset),
            )
        except Exception as e:
            unexpected_error(e, logger)
            raise e

    def __on_result(
        self,
        update: Update,
        context: CallbackContext,  # noqa: ARG002
    ) -> None:
        """Clear cached stickers after a chosen inline result."""
        try:
            user = update.effective_user
            chosen_result = update.chosen_inline_result

            # Parse Telegram data safely
            user_id = str(user.id) if user is not None else None

            # Build application command
            command = ClearInlineCacheCommand(
                user_id=user_id,
                query_text=chosen_result.query,
            )

            # Delegate to application layer
            self._clear_inline_cache(command)

            # Log success
            logger.info(f"Answered inline query for {chosen_result.query}")
        except Exception as e:
            unexpected_error(e, logger)

    def _build_help_article(self, result) -> InlineQueryResultArticle:
        """Convert application result into a Telegram help article."""
        display_title = "Click me for help"
        first_tag = result.default_tags[0] if result.default_tags else "help"
        return InlineQueryResultArticle(
            id=str(uuid4()),
            title=display_title,
            description=f"Try calling me inline like `@stickfixbot {first_tag}`",
            input_message_content=InputTextMessageContent(
                result.help_text,
                parse_mode=ParseMode.MARKDOWN,
            ),
        )
