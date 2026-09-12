""" "Stickfix" (c) by Ignacio Slater M.
"Stickfix" is licensed under a
Creative Commons Attribution 4.0 International License.

You should have received a copy of the license along with this
work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""

import logging

from telegram import Message, Sticker, Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, Dispatcher

from bot.application.errors import MissingStickerError, WrongInteractionContextError
from bot.application.requests import (
  AddStickerCommand,
  DeleteStickerCommand,
  GetStickersQuery,
  InteractionScope,
)
from bot.application.use_cases import AddSticker, DeleteSticker, GetStickers
from bot.handlers.common import StickfixHandler, caller_id
from bot.utils.errors import NoStickerException, WrongContextException, unexpected_error
from bot.utils.messages import (
  Commands,
  check_reply,
  check_sticker,
  get_message_meta,
  raise_wrong_context_error,
)

logger = logging.getLogger(__name__)

#: Errors already reported to the user by ``bot.utils.messages`` helpers; the
#: handler only needs to stop processing when one is raised.
_HANDLED_INPUT_ERRORS = (NoStickerException, MissingStickerError)


class StickerHandler(StickfixHandler):
  """Bridge the ``/add``, ``/get``, and ``/deleteFrom`` commands to their use cases.

  Each callback parses the Telegram update, delegates to an ``AddSticker`` /
  ``GetStickers`` / ``DeleteSticker`` use case, and turns the outcome into a reply.
  Validation of the replied-to sticker lives in ``bot.utils.messages`` and raises
  ``NoStickerException`` after already telling the user what went wrong.
  """

  def __init__(
    self,
    dispatcher: Dispatcher,
    add_sticker: AddSticker,
    get_stickers: GetStickers,
    delete_sticker: DeleteSticker,
  ):
    super().__init__(dispatcher)
    self.__add_sticker_use_case = add_sticker
    self.__get_stickers_use_case = get_stickers
    self.__delete_sticker_use_case = delete_sticker
    self._dispatcher.add_handler(CommandHandler(Commands.ADD, self.__add_sticker, pass_args=True))
    self._dispatcher.add_handler(CommandHandler(Commands.GET, self.__get_stickers, pass_args=True))
    self._dispatcher.add_handler(
      CommandHandler(Commands.DELETE_FROM, self.__delete_from, pass_args=True)
    )

  @staticmethod
  def __replied_sticker(message: Message, action: str = "add") -> Sticker:
    """Return the sticker the command replied to, or raise ``NoStickerException``."""
    reply_to = message.reply_to_message
    check_reply(reply_to, message, action)
    sticker = reply_to.sticker
    check_sticker(sticker, message)
    return sticker

  def __add_sticker(self, update: Update, context: CallbackContext) -> None:
    """Answers the /add command by adding the replied-to sticker to the DB."""
    try:
      msg, _, _ = get_message_meta(update)
      sticker = self.__replied_sticker(msg)
      self.__add_sticker_use_case(
        AddStickerCommand(
          user_id=caller_id(update),
          reply_sticker_id=sticker.file_id,
          reply_sticker_emoji=sticker.emoji,
          tags=tuple(context.args),
        )
      )
      msg.reply_text("Ok!")
    except _HANDLED_INPUT_ERRORS:
      logger.debug("Handled error.")
    except Exception as e:
      unexpected_error(e, logger)

  def __get_stickers(self, update: Update, context: CallbackContext) -> None:
    """Sends all the stickers linked with the requested tags (private chats only)."""
    try:
      message, user, chat = get_message_meta(update)
      query = GetStickersQuery(
        user_id=caller_id(update),
        interaction_scope=(
          InteractionScope.PRIVATE if chat.type == "private" else InteractionScope.NON_PRIVATE
        ),
        tags=tuple(context.args),
      )
      for sticker_id in self.__get_stickers_use_case(query).sticker_ids:
        chat.send_sticker(sticker_id)
    except WrongInteractionContextError:
      message.reply_text("This command only works in private chats.")
      self.__log_wrong_context(user.username, chat.type)
    except WrongContextException:
      logger.debug("Handled exception.")
    except BadRequest as e:
      raise e
    except Exception as e:
      unexpected_error(e, logger)

  def __delete_from(self, update: Update, context: CallbackContext) -> None:
    """Answers the /deleteFrom command by unlinking the replied-to sticker."""
    try:
      message, _, _ = get_message_meta(update)
      sticker = self.__replied_sticker(message, "remove")
      self.__delete_sticker_use_case(
        DeleteStickerCommand(
          user_id=caller_id(update),
          reply_sticker_id=sticker.file_id,
          tags=tuple(context.args),
        )
      )
    except _HANDLED_INPUT_ERRORS:
      logger.debug("Handled error.")
    except Exception as e:
      unexpected_error(e, logger)

  @staticmethod
  def __log_wrong_context(username: str, chat_type: str) -> None:
    """Log a `/get` used outside a private chat, after replying to the user."""
    try:
      raise_wrong_context_error(
        msg=f"Command /get called by user {username} raised an exception.",
        cause=f"Chat type is {chat_type}.",
      )
    except WrongContextException:
      logger.debug("Handled exception.")
