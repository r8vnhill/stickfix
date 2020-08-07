""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import json

from telegram import Message, Update
from telegram.ext import CallbackContext

from bot.logger import StickfixLogger

module_logger = StickfixLogger(__name__)


def get_message_content(update: Update):
    """ Gets the content of a telegram message  """
    message_content: Message = update.effective_message
    module_logger.debug(
        f"Received message: \n {json.dumps(message_content.to_dict(), indent=2, sort_keys=True)}")
    return message_content


def send_hello_message(update: Update, context: CallbackContext):
    """ Answers the /start command with a hello sticker """
    chat_id = update.effective_chat.id
    context.bot.send_sticker(chat_id, sticker='CAADBAADTAADqAABTgXzVqN6dJUIXwI')
