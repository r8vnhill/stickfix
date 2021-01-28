""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import random
from typing import List, Tuple
from uuid import uuid4

from telegram import InlineQuery, InlineQueryResult, InlineQueryResultArticle, \
    InlineQueryResultCachedSticker, InputTextMessageContent, ParseMode, Update, User
from telegram.ext import CallbackContext, ChosenInlineResultHandler, Dispatcher, InlineQueryHandler

from bot.database.storage import StickfixDB
from bot.database.users import SF_PUBLIC, StickfixUser
from bot.handlers.common import HELP_PATH, StickfixHandler
from bot.utils.errors import unexpected_error
from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)


class InlineHandler(StickfixHandler):
    def __init__(self, dispatcher: Dispatcher, user_db: StickfixDB):
        super().__init__(dispatcher, user_db)
        self._dispatcher.add_handler(InlineQueryHandler(self.__inline_get))
        self._dispatcher.add_handler(ChosenInlineResultHandler(self.__on_result))

    def __inline_get(self, update: Update, context: CallbackContext):
        """ Gets all the stickers linked with a list of tags and sends them as an inline query
            answer.
        """
        user: User
        inline_query: InlineQuery

        try:
            inline_query = update.inline_query
            query = inline_query.query
            user = update.effective_user
            sf_user = self._user_db[user.id] if user.id in self._user_db else self._user_db[
                SF_PUBLIC]
            offset = int(0 if not inline_query.offset else inline_query.offset)
            tags = str(query).split(" ")
            stickers = []
            if not offset and not query:
                tags, stickers = self.__send_default_answer(sf_user)
            sticker_list = self._get_sticker_list(sf_user, tags)
            upper_bound = min(len(sticker_list), offset + 49)
            if sf_user.shuffle:
                random.shuffle(sticker_list)
            for i in range(offset, upper_bound):
                stickers.append(
                    InlineQueryResultCachedSticker(id=uuid4(), sticker_file_id=sticker_list[i]))
            context.bot.answer_inline_query(inline_query.id, stickers, cache_time=1,
                                            is_personal=True, next_offset=str(offset + 49))
            self._user_db[sf_user.id] = sf_user
        except Exception as e:
            unexpected_error(e, logger)
            raise e

    # noinspection PyUnusedLocal
    def __on_result(self, update: Update, context: CallbackContext):
        user: User
        try:
            user = update.effective_user
            sf_user = self._user_db[user.id] if user.id in self._user_db else self._user_db[
                SF_PUBLIC]
            sf_user.remove_cached_stickers()
            self._user_db[sf_user.id] = sf_user
            logger.info(f"Answered inline query for {update.chosen_inline_result.query}")
        except Exception as e:
            unexpected_error(e, logger)

    def __send_default_answer(self, user: StickfixUser) -> Tuple[
        List[str], List[InlineQueryResult]]:
        results = []
        if user.private_mode:
            tags = user.random_tag()
        else:
            tags = self._user_db[SF_PUBLIC].random_tag()
        display_title = "Click me for help"
        with open(HELP_PATH, "r") as help_file:
            help_text = help_file.read()
        results.append(InlineQueryResultArticle(
            id=uuid4(), title=display_title,
            description=f"Try calling me inline like `@stickfixbot {tags[0]}`",
            input_message_content=InputTextMessageContent(help_text,
                                                          parse_mode=ParseMode.MARKDOWN)))
        return tags, results
