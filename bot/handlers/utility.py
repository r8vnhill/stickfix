""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
from telegram import ParseMode, Update
from telegram.ext import CallbackContext, CommandHandler, Dispatcher

from bot.database.storage import StickfixDB
from bot.database.users import Switch, UserModes
from bot.handlers.common import HELP_PATH, StickfixHandler
from bot.utils.errors import InputException, unexpected_error
from bot.utils.logger import StickfixLogger
from bot.utils.messages import Commands, get_message_meta, raise_input_error

logger = StickfixLogger(__name__)


def send_help_message(update: Update, context: CallbackContext) -> None:
    """ Sends a help message to the chat.   """
    try:
        _, _, chat = get_message_meta(update)
        with open(HELP_PATH, "r") as help_file:
            context.bot.send_message(chat_id=chat.id, text=help_file.read(),
                                     parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Sent help message to {chat.username}.")
    except Exception as e:
        unexpected_error(e, logger)


class HelperHandler(StickfixHandler):
    def __init__(self, dispatcher: Dispatcher, user_db: StickfixDB):
        super().__init__(dispatcher, user_db)
        self._dispatcher.add_handler(CommandHandler(Commands.START, self.__send_hello_message))
        self._dispatcher.add_handler(CommandHandler(Commands.HELP, send_help_message))

    def __send_hello_message(self, update: Update, context: CallbackContext) -> None:
        """ Answers the /start command with a hello sticker and adds the user to the database. """
        _, _, chat = get_message_meta(update)
        context.bot.send_sticker(chat.id, sticker='CAADBAADTAADqAABTgXzVqN6dJUIXwI')
        if chat.id not in self._user_db:
            self._create_user(chat.id)
            logger.info(f"User {chat.id} was added to the database.")


class UserHandler(StickfixHandler):
    def __init__(self, dispatcher: Dispatcher, user_db: StickfixDB):
        super().__init__(dispatcher, user_db)
        self._dispatcher.add_handler(CommandHandler(Commands.DELETE_ME, self.__remove_user))
        self._dispatcher.add_handler(CommandHandler(Commands.SET_MODE, self.__set_mode))
        self._dispatcher.add_handler(CommandHandler(Commands.SHUFFLE, self.__set_shuffle,
                                                    pass_args=True))

    # noinspection PyUnusedLocal
    def __remove_user(self, update: Update, context: CallbackContext) -> None:
        """ Removes a user from the database.   """
        try:
            message, user, _ = get_message_meta(update)
            if user.id in self._user_db:
                del self._user_db[user.id]
                logger.info(f"User {user.id} was removed from the database.")
                message.reply_text("Sure!")
        except Exception as e:
            unexpected_error(e, logger)

    def __set_mode(self, update: Update, context: CallbackContext) -> None:
        """ Sets a user mode to private or public.   """
        try:
            message, user, chat = get_message_meta(update)
            if context.args:
                if user.id not in self._user_db:
                    self._create_user(user.id)
                mode = context.args[0].upper()
                sf_user = self._user_db[user.id]
                if mode == UserModes.PRIVATE or mode == UserModes.PUBLIC:
                    sf_user.private_mode = mode == UserModes.PRIVATE
                    message.reply_text("Leave it to me!")
                    logger.info(f"Changed {user.username} to {mode} mode.")
                else:
                    message.reply_markdown(
                        "Sorry, I didn't understand. This command syntax is `/setMode private` "
                        "or `setMode public`.")
                    raise_input_error(cause=f"{mode} is not a valid argument.",
                                      msg=f"Command /setMode called by user {user.username} "
                                          f"raised an exception.")
        except InputException:
            logger.debug("Handled exception.")
        except Exception as e:
            unexpected_error(e, logger)

    def __set_shuffle(self, update: Update, context: CallbackContext) -> None:
        """ Turns on or off the shuffle flag for the user. """
        try:
            message, user, _ = get_message_meta(update)
            if user.id not in self._user_db:
                self._create_user(user.id)
            sf_user = self._user_db[user.id]
            if context.args[0] == Switch.ON or context.args[0] == Switch.OFF:
                sf_user.shuffle = context.args[0] == Switch.ON
                logger.info(f"User {user.username} turned {context.args[0]} shuffle.")
            self._user_db[user.id] = sf_user
            message.reply_text("Done")
        except Exception as e:
            unexpected_error(e, logger)
