""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import json
from enum import Enum
from typing import Union

from telegram import Message, Sticker, Update, User

from bot.utils.errors import NoStickerError
from bot.utils.logger import StickfixLogger

module_logger = StickfixLogger(__name__)


def get_message_content(update: Update):
    """ Gets the content of a telegram message  """
    message_content: Message = update.effective_message
    module_logger.debug(
        f"Received message: \n {json.dumps(message_content.to_dict(), indent=2, sort_keys=True)}")
    return message_content


def check_reply(reply: Union[Message, None], message: Message):
    """ Checks if a received message replies to another.    """
    if not reply:
        message.reply_markdown(
            "To add a sticker to the database, you need to *reply to a message* containing "
            "the sticker you want to add.")
        user: User = message.from_user
        raise_no_sticker_error(msg=add_error_msg(user.username),
                               cause="The user didn't reply to a sticker.")


def check_sticker(sticker: Union[Sticker, None], message: Message):
    """ Checks if a message contains a sticker.    """
    if not sticker:
        message.reply_markdown("I can only add stickers to de database.")
        user: User = message.from_user
        raise_no_sticker_error(msg=add_error_msg(user.username),
                               cause="The command didn't reply to a sticker")


def add_error_msg(user: str) -> str:
    return f"Command /add called by user {user} raised an exception."


def raise_no_sticker_error(msg: str, cause: str):
    error = NoStickerError(err_message=msg, err_cause=cause)
    module_logger.error(error.message)
    module_logger.error(error.cause)
    raise error


class Commands(str, Enum):
    START = "start"
    ADD = "add"
    HELP = "help"
