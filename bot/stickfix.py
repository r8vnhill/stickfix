""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
from typing import List

from telegram.ext import CommandHandler, Dispatcher, Updater

import bot.messages
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

    def run(self) -> None:
        """ Runs the bot.   """
        self.__logger.info("Starting bot polling service.")
        self.__updater.start_polling()

    def __start_updater(self, token: str) -> None:
        """ Starts the bot's updater with the given token.  """
        self.__logger.info(f"Starting bot updater")
        self.__updater = Updater(token, use_context=True)

    def __setup_handlers(self):
        self.__dispatcher.add_handler(CommandHandler("start", bot.messages.send_hello_message))
