""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import random
from typing import List

from telegram import Message, Sticker, Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, Dispatcher

from bot.database.storage import StickfixDB
from bot.database.users import SF_PUBLIC, UserModes
from bot.handlers.common import StickfixHandler
from bot.utils.errors import NoStickerException, WrongContextException, unexpected_error
from bot.utils.logger import StickfixLogger
from bot.utils.messages import Commands, check_reply, check_sticker, get_message_meta, \
    raise_wrong_context_error

logger = StickfixLogger(__name__)


class StickerHandler(StickfixHandler):
    def __init__(self, dispatcher: Dispatcher, user_db: StickfixDB):
        super().__init__(dispatcher, user_db)
        self._dispatcher.add_handler(
            CommandHandler(Commands.ADD, self.__add_sticker, pass_args=True))
        self._dispatcher.add_handler(
            CommandHandler(Commands.GET, self.__get_stickers, pass_args=True))
        self._dispatcher.add_handler(
            CommandHandler(Commands.DELETE_FROM, self.__delete_from, pass_args=True))
        self._dispatcher.add_handler(
            CommandHandler(Commands.WTF, self.__wtf, pass_args=False))

    def __add_sticker(self, update: Update, context: CallbackContext) -> None:
        """ Answers the /add command by adding a sticker to the DB. """
        sticker: Sticker
        reply_to: Message
        try:
            if SF_PUBLIC not in self._user_db:
                self._create_user(SF_PUBLIC)
                logger.info(f"Created {SF_PUBLIC} user.")
            msg, user, chat = get_message_meta(update)
            reply_to: Message = msg.reply_to_message
            check_reply(reply_to, msg)
            sticker = reply_to.sticker
            check_sticker(sticker, msg)
            emoji = [sticker.emoji] if sticker.emoji else []
            tags = context.args if context.args else emoji
            self.__link_tags(sticker, tags, msg)
        except NoStickerException:
            logger.debug("Handled error.")
        except Exception as e:
            unexpected_error(e, logger)

    def __get_stickers(self, update: Update, context: CallbackContext) -> None:
        """ Sends all the stickers linked with a tag.   """
        try:
            message, user, chat = get_message_meta(update)
            if chat.type != UserModes.PRIVATE:
                message.reply_text("This command only works in private chats.")
                raise_wrong_context_error(
                    msg=f"Command /get called by user {user.username} raised an exception.",
                    cause=f"Chat type is {chat.type}.")
            sf_user = self._user_db[user.id] if user.id in self._user_db else self._user_db[
                SF_PUBLIC]
            stickers = self._get_sticker_list(sf_user, context.args)
            for sticker_id in stickers:
                chat.send_sticker(sticker_id)
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
            message, user, _ = get_message_meta(update)
            reply_to = message.reply_to_message
            check_reply(reply_to, message, "remove")
            sticker = reply_to.sticker
            check_sticker(sticker, message)
            tags = context.args
            sf_user = self._user_db[user.id] if user.id in self._user_db else self._user_db[
                SF_PUBLIC]
            if not sf_user.private_mode:
                sf_user = self._user_db[SF_PUBLIC]
            sf_user.unlink_sticker(sticker.file_id, tags)
            self._user_db[user.id] = sf_user
        except NoStickerException:
            logger.debug("Handled error.")
        except Exception as e:
            unexpected_error(e, logger)

    def __link_tags(self, sticker: Sticker, tags: List[str], origin: Message):
        """ Links a list of tags with a sticker.    """
        if tags:
            user_id = origin.from_user.id
            user = self._user_db[user_id] if user_id in self._user_db else self._user_db[
                SF_PUBLIC]
            effective_user = user if user.private_mode else self._user_db[SF_PUBLIC]
            effective_user.add_sticker(sticker_id=sticker.file_id, sticker_tags=tags)
            self._user_db[user.id] = effective_user
            self._user_db.save()
        origin.reply_text("Ok!")

    def __wtf(self, update: Update, _: CallbackContext) -> None:
        try:
            message, user, chat = get_message_meta(update)
            sf_user = self._user_db[SF_PUBLIC]
            stickers = self._get_sticker_list(sf_user, ["👀"])
            message.reply_sticker(random.choice(stickers))
        except WrongContextException:
            logger.debug("Handled exception.")
        except BadRequest as e:
            raise e
        except Exception as e:
            unexpected_error(e, logger)
