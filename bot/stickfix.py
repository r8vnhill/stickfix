""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
from typing import List

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, Dispatcher, Updater

from bot.database.storage import StickfixDB
from bot.database.users import StickfixUser
from bot.logger import StickfixLogger


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
        self.__user_db = StickfixDB("stickfix-user-DB")

    def run(self) -> None:
        """ Runs the bot.   """
        self.__logger.info("Starting bot polling service.")
        self.__updater.start_polling()

    def __start_updater(self, token: str) -> None:
        """ Starts the bot's updater with the given token.  """
        self.__logger.info(f"Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    def __setup_handlers(self):
        self.__dispatcher.add_handler(CommandHandler("start", self.__send_hello_message))

    def __send_hello_message(self, update: Update, context: CallbackContext) -> None:
        """ Answers the /start command with a hello sticker and adds the user to the database. """
        chat_id = update.effective_chat.id
        context.bot.send_sticker(chat_id, sticker='CAADBAADTAADqAABTgXzVqN6dJUIXwI')
        if chat_id not in self.__user_db:
            self.__create_user(chat_id)
            self.__logger.info(f"User {chat_id} was added to the database.")

    def __create_user(self, chat_id: str) -> None:
        """ Creates and adds a user to the database.    """
        user = StickfixUser(chat_id)
        self.__user_db.add_item(chat_id, user)
