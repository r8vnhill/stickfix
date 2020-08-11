""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import random
from typing import List

from telegram import Message, Sticker, Update, User
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, Dispatcher, Updater

from bot.database.storage import StickfixDB
from bot.database.users import StickfixUser, Switch, UserModes
from bot.utils.errors import InputError, NoStickerError, WrongContextError
from bot.utils.logger import StickfixLogger
from bot.utils.messages import Commands, check_reply, check_sticker, \
    get_message_meta, \
    raise_input_error, \
    raise_wrong_context_error, send_help_message

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
        self.__dispatcher.add_handler(
            CommandHandler(Commands.ADD, self.__add_sticker, pass_args=True))
        self.__dispatcher.add_handler(CommandHandler(Commands.HELP, self.__send_help_message))
        self.__dispatcher.add_handler(CommandHandler(Commands.DELETE_ME, self.__remove_user))
        self.__dispatcher.add_handler(CommandHandler(Commands.SET_MODE, self.__set_mode))
        self.__dispatcher.add_handler(
            CommandHandler(Commands.GET, self.__get_stickers, pass_args=True))
        self.__dispatcher.add_handler(CommandHandler(Commands.SHUFFLE, self.__set_shuffle,
                                                     pass_args=True))

    def __send_hello_message(self, update: Update, context: CallbackContext) -> None:
        """ Answers the /start command with a hello sticker and adds the user to the database. """
        chat_id = update.effective_chat.id
        context.bot.send_sticker(chat_id, sticker='CAADBAADTAADqAABTgXzVqN6dJUIXwI')
        if chat_id not in self.__user_db:
            self.__create_user(chat_id)
            self.__logger.info(f"User {chat_id} was added to the database.")

    def __add_sticker(self, update: Update, context: CallbackContext) -> None:
        """ Answers the /add command by adding a sticker to the DB. """
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
            message, user, chat = get_message_meta(update)
            message = update.effective_message
            user = update.effective_user
            if user.id in self.__user_db:
                del self.__user_db[user.id]
                self.__logger.info(f"User {user.id} was removed from the database.")
                message.reply_text("Sure!")
        except Exception as e:
            self.__unexpected_error(e)

    def __set_mode(self, update: Update, context: CallbackContext) -> None:
        """ Sets a user mode to private or public.   """
        try:
            message, user, chat = get_message_meta(update)
            if context.args:
                if user.id not in self.__user_db:
                    self.__create_user(user.id)
                mode = context.args[0].upper()
                sf_user = self.__user_db[user.id]
                if mode == UserModes.PRIVATE or mode == UserModes.PUBLIC:
                    sf_user.private_mode = mode == UserModes.PRIVATE
                    message.reply_text("Leave it to me!")
                    self.__logger.info(f"Changed {user.username} to {mode} mode.")
                else:
                    message.reply_markdown(
                        "Sorry, I didn't understand. This command syntax is `/setMode private` "
                        "or `setMode public`.")
                    raise_input_error(cause=f"{mode} is not a valid argument.",
                                      msg=f"Command /setMode called by user {user.username} "
                                          f"raised an exception.")
        except InputError:
            self.__logger.debug("Handled exception.")
        except Exception as e:
            self.__unexpected_error(e)

    def __get_stickers(self, update: Update, context: CallbackContext) -> None:
        """ Sends all the stickers linked with a tag.   """
        try:
            message, user, chat = get_message_meta(update)
            if chat.type != UserModes.PRIVATE:
                message.reply_text("This command only works in private chats.")
                raise_wrong_context_error(
                    msg=f"Command /get called by user {user.username} raised an exception.",
                    cause=f"Chat type is {chat.type}.")
            sf_user = self.__user_db[user.id] if user.id in self.__user_db else self.__user_db[
                SF_PUBLIC]
            stickers = self.__get_sticker_list(sf_user, context.args)
            for sticker_id in stickers:
                chat.send_sticker(sticker_id)
        except WrongContextError:
            self.__logger.debug("Handled exception.")
        except BadRequest as e:
            raise e
        except Exception as e:
            self.__unexpected_error(e)

    def __set_shuffle(self, update: Update, context: CallbackContext) -> None:
        """ Turns on or off the shuffle flag for the user. """
        try:
            message, user, _ = get_message_meta(update)
            if user.id not in self.__user_db:
                self.__create_user(user.id)
            sf_user = self.__user_db[user.id]
            if context.args[0] == Switch.ON or context.args[0] == Switch.OFF:
                sf_user.shuffle = context.args[0] == Switch.ON
                self.__logger.info(f"User {user.username} turned {context.args[0]} shuffle.")
            self.__user_db[user.id] = sf_user
            message.reply_text("Done")
        except Exception as e:
            self.__unexpected_error(e)

    def __create_user(self, chat_id: str) -> None:
        """ Creates and adds a user to the database.    """
        self.__user_db[chat_id] = StickfixUser(chat_id)
        self.__logger.info(f"Created user with id {chat_id}")

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
            self.__user_db[user.id] = effective_user
        origin.reply_text("Ok!")

    def __get_sticker_list(self, user: StickfixUser, tags: List[str]):
        """ Returns the list of stickers associated with a tag and a user.  """
        stickers = []
        for tag in tags:
            self.__logger.info(f"Getting stickers matching {tag}")
            match = self.__user_db[user.id]
            if not user.private_mode:
                match = self.__user_db[SF_PUBLIC].get_stickers(tag)
            stickers.append(match.union(user.get_stickers(tag)))
        stickers = list(set.intersection(*stickers))
        if user.shuffle:
            random.shuffle(stickers)
        return stickers
