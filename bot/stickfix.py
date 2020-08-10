""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
from typing import List

from telegram import Message, Sticker, Update, User
from telegram.ext import CallbackContext, CommandHandler, Dispatcher, Updater

from bot.database.storage import StickfixDB
from bot.database.users import StickfixUser
from bot.utils.errors import NoStickerError
from bot.utils.logger import StickfixLogger
from bot.utils.messages import Commands, check_reply, check_sticker, send_help_message

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
    __admins: List[int]
    __user_db: StickfixDB

    def __init__(self, token: str, admins: List[int]):
        """ Initializes the bot.

        :param token:
            the bot's telegram token
        :param admins:
            list of the ids of the users who have admin privileges over the bot
        """
        self.__logger = StickfixLogger(__name__)
        self.__start_updater(token)
        self.__admins = admins
        self.__dispatcher = self.__updater.dispatcher
        self.__setup_handlers()
        self.__user_db = StickfixDB(USERS_DB)

    def run(self) -> None:
        """ Runs the bot.   """
        self.__logger.info("Starting bot polling service.")
        self.__updater.start_polling()

    def __start_updater(self, token: str) -> None:
        """ Starts the bot's updater with the given token.  """
        self.__logger.info(f"Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    def __setup_handlers(self):
        self.__dispatcher.add_handler(CommandHandler(Commands.START, self.__send_hello_message))
        self.__dispatcher.add_handler(CommandHandler(Commands.ADD, self.__add_sticker))
        self.__dispatcher.add_handler(CommandHandler(Commands.HELP, self.__send_help_message))
        self.__dispatcher.add_handler(CommandHandler(Commands.DELETE_ME, self.__remove_user))

    def __send_hello_message(self, update: Update, context: CallbackContext) -> None:
        """ Answers the /start command with a hello sticker and adds the user to the database. """
        chat_id = update.effective_chat.id
        context.bot.send_sticker(chat_id, sticker='CAADBAADTAADqAABTgXzVqN6dJUIXwI')
        if chat_id not in self.__user_db:
            self.__create_user(chat_id)
            self.__logger.info(f"User {chat_id} was added to the database.")

    def __add_sticker(self, update: Update, context: CallbackContext) -> None:
        """ Ansters the /add command by adding a sticker to the DB. """
        sticker: Sticker
        try:
            if SF_PUBLIC not in self.__user_db:
                self.__create_user(SF_PUBLIC)
                self.__logger.info(f"Created {SF_PUBLIC} user.")
            msg: Message = update.effective_message
            reply_to: Message = msg.reply_to_message
            check_reply(reply_to, msg)
            sticker = reply_to.sticker
            check_sticker(sticker, msg)
            emoji = [sticker.emoji] if sticker.emoji else []
            tags = context.args if context.args else emoji
            self.__link_tags(sticker, tags, msg)
        except NoStickerError:
            self.__logger.debug("Handled error.")
        except Exception as e:
            self.__unexpected_error(e)

    def __send_help_message(self, update: Update, context: CallbackContext) -> None:
        """ Sends a help message to the chat.   """
        try:
            send_help_message(update, context)
        except Exception as e:
            self.__unexpected_error(e)

    # noinspection PyUnusedLocal
    def __remove_user(self, update: Update, context: CallbackContext) -> None:
        """ Removes a user from the database.   """
        user: User
        message: Message
        try:
            message = update.effective_message
            user = update.effective_user
            user_id = user.id
            if user_id in self.__user_db:
                del self.__user_db[user_id]
                self.__logger.info(f"User {user_id} was removed from the database.")
                message.reply_text("Sure!")
        except Exception as e:
            self.__unexpected_error(e)

    def __create_user(self, chat_id: str) -> None:
        """ Creates and adds a user to the database.    """
        self.__user_db[chat_id] = StickfixUser(chat_id)

    def __unexpected_error(self, e: Exception):
        """ Logs an unhandled exception.    """
        self.__logger.critical("Unexpected error")
        self.__logger.critical(str(type(e)))
        self.__logger.critical(str(e.args))

    def __link_tags(self, sticker: Sticker, tags: List[str], origin: Message):
        """ Links a list of tags with a sticker.    """
        if tags:
            user_id = origin.from_user.id
            user = self.__user_db[user_id] if user_id in self.__user_db else self.__user_db[
                SF_PUBLIC]
            effective_user = user if user.private_mode else self.__user_db[SF_PUBLIC]
            effective_user.add_sticker(sticker_id=sticker.file_id, sticker_tags=tags)
            self.__user_db[user_id] = effective_user
        origin.reply_text("Ok!")
