""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
from telegram import Message, Sticker, Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, Dispatcher

from bot.application.errors import MissingStickerError, WrongInteractionContextError
from bot.application.requests import AddStickerCommand, DeleteStickerCommand, GetStickersQuery
from bot.application.use_cases import AddSticker, DeleteSticker, GetStickers
from bot.database.storage import StickfixDB
from bot.handlers.common import StickfixHandler
from bot.infrastructure.persistence import StickfixUserRepository
from bot.utils.errors import NoStickerException, WrongContextException, unexpected_error
from bot.utils.logger import StickfixLogger
from bot.utils.messages import (
    Commands,
    check_reply,
    check_sticker,
    get_message_meta,
    raise_wrong_context_error,
)

logger = StickfixLogger(__name__)


class StickerHandler(StickfixHandler):
    def __init__(self, dispatcher: Dispatcher, user_db: StickfixDB):
        super().__init__(dispatcher, user_db)
        user_repository = StickfixUserRepository(user_db)
        self.__add_sticker_use_case = AddSticker(user_repository)
        self.__get_stickers_use_case = GetStickers(user_repository)
        self.__delete_sticker_use_case = DeleteSticker(user_repository)
        self._dispatcher.add_handler(
            CommandHandler(Commands.ADD, self.__add_sticker, pass_args=True))
        self._dispatcher.add_handler(
            CommandHandler(Commands.GET, self.__get_stickers, pass_args=True))
        self._dispatcher.add_handler(
            CommandHandler(Commands.DELETE_FROM, self.__delete_from, pass_args=True))

    def __add_sticker(self, update: Update, context: CallbackContext) -> None:
        """ Answers the /add command by adding a sticker to the DB. """
        sticker: Sticker
        reply_to: Message
        try:
            msg, user, chat = get_message_meta(update)
            reply_to: Message = msg.reply_to_message
            check_reply(reply_to, msg)
            sticker = reply_to.sticker
            check_sticker(sticker, msg)
            command = AddStickerCommand(
                user_id=user.id,
                chat_id=chat.id,
                chat_type=chat.type,
                reply_sticker_id=sticker.file_id,
                reply_sticker_emoji=sticker.emoji,
                tags=tuple(context.args),
            )
            self.__add_sticker_use_case(command)
            msg.reply_text("Ok!")
        except NoStickerException:
            logger.debug("Handled error.")
        except MissingStickerError:
            logger.debug("Handled error.")
        except Exception as e:
            unexpected_error(e, logger)

    def __get_stickers(self, update: Update, context: CallbackContext) -> None:
        """ Sends all the stickers linked with a tag.   """
        try:
            message, user, chat = get_message_meta(update)
            query = GetStickersQuery(
                user_id=user.id,
                chat_id=chat.id,
                chat_type=chat.type,
                tags=tuple(context.args),
            )
            result = self.__get_stickers_use_case(query)
            for sticker_id in result.sticker_ids:
                chat.send_sticker(sticker_id)
        except WrongInteractionContextError:
            message.reply_text("This command only works in private chats.")
            try:
                raise_wrong_context_error(
                    msg=f"Command /get called by user {user.username} raised an exception.",
                    cause=f"Chat type is {chat.type}.")
            except WrongContextException:
                logger.debug("Handled exception.")
        except WrongContextException:
            logger.debug("Handled exception.")
        except BadRequest as e:
            raise e
        except Exception as e:
            unexpected_error(e, logger)

    def __delete_from(self, update: Update, context: CallbackContext) -> None:
        """ Deletes a sticker from the database. """
        sticker: Sticker
        try:
            message, user, chat = get_message_meta(update)
            reply_to = message.reply_to_message
            check_reply(reply_to, message, "remove")
            sticker = reply_to.sticker
            check_sticker(sticker, message)
            command = DeleteStickerCommand(
                user_id=user.id,
                chat_id=chat.id,
                chat_type=chat.type,
                reply_sticker_id=sticker.file_id,
                tags=tuple(context.args),
            )
            self.__delete_sticker_use_case(command)
        except NoStickerException:
            logger.debug("Handled error.")
        except MissingStickerError:
            logger.debug("Handled error.")
        except Exception as e:
            unexpected_error(e, logger)
