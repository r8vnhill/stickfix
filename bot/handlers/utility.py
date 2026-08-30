""" "Stickfix" (c) by Ignacio Slater M.
"Stickfix" is licensed under a
Creative Commons Attribution 4.0 International License.

You should have received a copy of the license along with this
work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""

from telegram import ParseMode, Update
from telegram.ext import CallbackContext, CommandHandler, Dispatcher

from bot.application.errors import InvalidCommandInputError
from bot.application.ports import UserRepository
from bot.application.requests import (
    DeleteUserCommand,
    EnsureUserCommand,
    SetModeCommand,
    SetShuffleCommand,
)
from bot.application.use_cases import DeleteUser, EnsureUser, SetMode, SetShuffle
from bot.handlers.common import HELP_PATH, StickfixHandler, caller_id
from bot.utils.errors import unexpected_error
from bot.utils.logger import StickfixLogger
from bot.utils.messages import Commands, get_message_meta

logger = StickfixLogger(__name__)


def send_help_message(update: Update, context: CallbackContext) -> None:
    """Send the contents of ``HELP.md`` to the chat as Markdown (module-level so
    `/help` works without a per-user record)."""
    try:
        _, _, chat = get_message_meta(update)
        with open(HELP_PATH, "r", encoding="utf-8") as help_file:
            context.bot.send_message(
                chat_id=chat.id, text=help_file.read(), parse_mode=ParseMode.MARKDOWN
            )
        logger.info(f"Sent help message to {chat.username}.")
    except Exception as e:
        unexpected_error(e, logger)


class HelperHandler(StickfixHandler):
    """Handle `/start` (greet + register the caller) and `/help` (send HELP.md)."""

    def __init__(self, dispatcher: Dispatcher, users: UserRepository):
        super().__init__(dispatcher, users)
        self.__ensure_user_use_case = EnsureUser(users)
        self._dispatcher.add_handler(CommandHandler(Commands.START, self.__send_hello_message))
        self._dispatcher.add_handler(CommandHandler(Commands.HELP, send_help_message))

    def __send_hello_message(self, update: Update, context: CallbackContext) -> None:
        """Answers the /start command with a hello sticker and adds the user to the database."""
        _, _, chat = get_message_meta(update)
        context.bot.send_sticker(chat.id, sticker="CAADBAADTAADqAABTgXzVqN6dJUIXwI")
        if update.effective_user is not None:
            self.__ensure_user_use_case(EnsureUserCommand(caller_id(update)))
            logger.info(f"User {chat.id} was added to the database.")


class UserHandler(StickfixHandler):
    """Handle the per-user preference/lifecycle commands: `/setMode`, `/shuffle`, `/deleteMe`."""

    def __init__(self, dispatcher: Dispatcher, users: UserRepository):
        super().__init__(dispatcher, users)
        self.__set_mode_use_case = SetMode(users)
        self.__set_shuffle_use_case = SetShuffle(users)
        self.__delete_user_use_case = DeleteUser(users)
        self._dispatcher.add_handler(CommandHandler(Commands.DELETE_ME, self.__remove_user))
        self._dispatcher.add_handler(CommandHandler(Commands.SET_MODE, self.__set_mode))
        self._dispatcher.add_handler(
            CommandHandler(Commands.SHUFFLE, self.__set_shuffle, pass_args=True)
        )

    # noinspection PyUnusedLocal
    def __remove_user(self, update: Update, context: CallbackContext) -> None:
        """Removes a user from the database."""
        try:
            message, user, _ = get_message_meta(update)
            result = self.__delete_user_use_case(DeleteUserCommand(caller_id(update)))
            if result.acknowledged:
                logger.info(f"User {user.id} was removed from the database.")
                message.reply_text("Sure!")
        except Exception as e:
            unexpected_error(e, logger)

    def __set_mode(self, update: Update, context: CallbackContext) -> None:
        """Sets a user mode to private or public."""
        try:
            message, user, chat = get_message_meta(update)
            if context.args:
                mode = context.args[0]
                command = SetModeCommand(user_id=caller_id(update), mode=mode)
                self.__set_mode_use_case(command)
                message.reply_text("Leave it to me!")
                logger.info(f"Changed {user.username} to {mode} mode.")
        except InvalidCommandInputError:
            message.reply_markdown(
                "Sorry, I didn't understand. This command syntax is `/setMode private` "
                "or `setMode public`."
            )
            logger.debug("Handled exception.")
        except Exception as e:
            unexpected_error(e, logger)

    def __set_shuffle(self, update: Update, context: CallbackContext) -> None:
        """Turns on or off the shuffle flag for the user."""
        try:
            message, user, _ = get_message_meta(update)
            switch = context.args[0]
            self.__set_shuffle_use_case(
                SetShuffleCommand(user_id=caller_id(update), shuffle=switch)
            )
            logger.info(f"User {user.username} turned {switch} shuffle.")
            message.reply_text("Done")
        except Exception as e:
            unexpected_error(e, logger)
