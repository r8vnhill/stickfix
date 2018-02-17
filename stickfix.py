#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bot that helps storing and sending stickers in telegram.
"""

import logging
import random
from shutil import copyfile
from traceback import format_exc
from uuid import uuid4

from telegram import InlineQueryResultArticle, InlineQueryResultCachedSticker, InputTextMessageContent, ParseMode
from telegram.error import BadRequest, ChatMigrated, NetworkError, TelegramError, TimedOut, Unauthorized
from telegram.ext import ChosenInlineResultHandler, CommandHandler, InlineQueryHandler, Updater

from sf_database import ShelveDB
from sf_exceptions import InputError, InsufficientPermissionsError, NoStickerError, WrongContextError
from sf_user import StickfixUser

__author__ = "Ignacio Slater Muñoz <ignacio.slater@ug.uchile.cl>"
__version__ = "2.1"

# TODO -cAdd -v2.2 : Implementar comando `/addSet`.
# Revisar http://python-telegram-bot.readthedocs.io/en/stable/telegram.html `get_sticker_set`   —Ignacio.

HELP_MESSAGE = ("Yo! I'm StickFix, I can link keywords with stickers so you can manage them more easily. By "
                "default, all tags are public (everyone can access them), but you can also create your own "
                "_private collection_ of stickers.\n"
                "You can use any word or even emojis as tags, so for example, you can link a sticker with the tag "
                "`hello`. \n"
                "To use this bot, you simply have to call it inline like `@stickfixbot tag`, and it will show a "
                "list with all the stickers linked with `tag`. You can even use more than one tag and the bot "
                "will search for all the stickers that have all those tags in common.",
                "*You can control me by sending me these commands:*\n"
                "`/add tags` - Links a sticker with one or more tags. For this to work you have to reply to a "
                "message that contains a sticker with the command; I need access to the messages to do this.\n"
                "`/deleteFrom tags` - Is similar to `/add`, but this removes a sticker from a tag.\n"
                "`/setMode (private|public)` - Changes the user to public or private mode. In private mode only "
                "you will be able to see the stickers you add; by default all users are in public mode.\n"
                "`/shuffle (on|off)` - Turn this on if you want the stickers in inline mode to be shown in "
                "random order; it's off by default.\n"
                "`/deleteMe` - If you want to be removed from the database. This will erase all the stickers you "
                "added in private mode and can't be undone.",
                )


class StickfixBot:
    """
    Base class for @stickfixbot.
    This class implements functions to help manage and store stickers in
    telegram using chat commands and inline queries.
    """

    def __init__(self, token, admins):
        """
        Initializes the bot.

        :param token:
            Bot's TOKEN.
        :param admins:
            List containing the id's of the users with admin privilege.
        """
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
        self._admins = admins
        self._current_backup_id = 0
        self.user_db = ShelveDB("stickfix-user-DB")
        self._logger = logging.getLogger(__name__)
        self._empty_db = False  # Indica si se borró la bdd manualmente.
        
        self._updater = Updater(token)
        self.dispatcher = self._updater.dispatcher

        self.job_queue = self._updater.job_queue
        self.job_queue.run_repeating(self.periodic_backup, interval=43200, first=0)
        self.job_queue.run_repeating(self.periodic_database_check, interval=3600, first=1800)
        self.job_queue.run_repeating(self.periodic_cache_remove, interval=259200, first=0)
        
        # region Handlers
        self.dispatcher.add_handler(CommandHandler("start", self.cmd_start))
        self.dispatcher.add_handler(CommandHandler("help", self.cmd_help))
        self.dispatcher.add_handler(CommandHandler("deleteMe", self.cmd_delete_user))
        self.dispatcher.add_handler(CommandHandler("getDB", self.cmd_get_db))
        self.dispatcher.add_handler(CommandHandler("setMode", self.cmd_set_mode, pass_args=True))
        self.dispatcher.add_handler(CommandHandler("add", self.cmd_add, pass_args=True))
        self.dispatcher.add_handler(CommandHandler('get', self.cmd_get, pass_args=True))
        self.dispatcher.add_handler(CommandHandler("shuffle", self.cmd_set_shuffle, pass_args=True))
        self.dispatcher.add_handler(CommandHandler("deleteFrom", self.cmd_delete_from, pass_args=True))
        self.dispatcher.add_handler(CommandHandler("restore", self.cmd_restore, pass_args=True))
        self.dispatcher.add_handler(InlineQueryHandler(self._inline_get))
        self.dispatcher.add_handler(ChosenInlineResultHandler(self._on_inline_result))
        # endregion
        self.dispatcher.add_error_handler(self._error_callback)  # Para logging de errores.
    
    def run(self):
        """
        Starts the bot.
        """
        self._updater.start_polling()

    # region Chat commands
    def cmd_add(self, bot, update, args):
        """
        Adds a sticker to the database.
        
        :param args:
            Tags that identify the pack to which the stickers are going to be added.
        """
        # Se debe crear el usuario SF-PUBLIC si no existe.
        try:
            if 'SF-PUBLIC' not in self.user_db:
                self._create_user('SF-PUBLIC')
                self._logger.info('Created SF-PUBLIC user.')
    
            tg_reply_to = update.effective_message.reply_to_message
            tg_msg = update.message
            tg_user = update.effective_user
            tg_user_id = str(tg_user.id)
            if tg_reply_to is None:  # Si no se responde a ningún mensaje.
                tg_msg.reply_text(
                    "To add a sticker to the database, you need to *reply to a message* containing the sticker you "
                    "want to add.",
                    parse_mode=ParseMode.HTML)
                raise NoStickerError(
                    err_message="Command /add called by user " + tg_user.username + " raised an exception.",
                    err_cause="reply_to_message is None.")
            tg_sticker = tg_reply_to.sticker
            if tg_sticker is None:  # Si el mensaje al que se responde no contiene ningún sticker.
                tg_msg.reply_text("I can only add stickers to de database.")
                raise NoStickerError(
                    err_message="Command /add called by user " + tg_user.username + " raised an exception.",
                    err_cause="sticker is None")
    
            if len(args) == 0:  # Si no se especifica un tag, se toma el emoji asociado al sticker.
                tags = [tg_sticker.emoji]
            else:
                tags = args
            if tags is not None:
                tg_username = tg_user.username
                sf_user = self.user_db.get_item(tg_user_id) if tg_user_id in self.user_db else None
                
                if sf_user is None or sf_user.private_mode == StickfixUser.OFF:
                    # Si el usuario no existe o está en modo público, se considera el usuario como `SF-PUBLIC`
                    sf_user = self.user_db.get_item('SF-PUBLIC')
                    tg_username = 'stickfix-public'

                sf_user.add_sticker(sticker_id=tg_sticker.file_id, sticker_tags=tags)
                self.user_db.add_item(sf_user.id, sf_user)
                self._logger.info("Sticker added to %s's pack with tags: " + ', '.join(tags), tg_username)
                tg_msg.reply_text("Ok.")
        except NoStickerError as e:
            self._log_error(e)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /add command with "
                                       "parameters: " + ", ".join(args) + ".")

    def cmd_delete_from(self, bot, update, args):
        """
        Deletes a sticker from the database.
        
        :param args:
            List with the tags from which the sticker is going to be removed.
        """
        try:
            tg_user = update.effective_user
            tg_reply_to = update.effective_message.reply_to_message
            if len(args) == 0:
                update.message.reply_text("You need to give me at least 1 tag to search for stickers.")
                raise InputError(
                    err_message="Command /deleteFrom called by user " + tg_user.username + " raised an exception.",
                    err_cause="Not enough arguments.")
            if tg_reply_to is None:
                # Si no se responde a ningún mensaje ni se llamó el comando de manera especial.
                update.message.reply_text(
                    "To delete a sticker from the database, you need to *reply to a message* containing the sticker "
                    "you want to remove.",
                    parse_mode=ParseMode.HTML)
                raise NoStickerError(
                    err_message="Command /deleteFrom called by user " + tg_user.username + " raised an exception.",
                    err_cause="reply_to_message is None.")
            tg_sticker = tg_reply_to.sticker
            if tg_sticker is None:  # Si el mensaje al que se responde no contiene ningún sticker.
                update.message.reply_text("The message you replied to doesn't contain a sticker.")
                raise NoStickerError(
                    err_message="Command /deleteFrom called by user " + tg_user.username + " raised an exception.",
                    err_cause="sticker is None")
            self._delete_from(update, tg_user, args)
            update.message.reply_text("Ok.")
        except InputError as e:
            self._log_error(e)
        except NoStickerError as e:
            self._log_error(e)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /deleteFrom command with "
                                       "parameters: " + ", ".join(args) + ".")

    def cmd_delete_user(self, bot, update):
        """Deletes the user who sent the command from the database."""
        try:
            tg_user = update.effective_user
            tg_user_id = str(tg_user.id)
            # TODO -cAdd -v2.2 : Pedir confirmación al usuario  —Ignacio.
            if tg_user_id in self.user_db:
                self.user_db.delete_by_key(tg_user_id)
                self._logger.info("User %s was removed from the database", tg_user.username)
                update.message.reply_text("Ok.")
            else:
                update.message.reply_text("You're not in my database.")
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /deleteMe command.")

    def cmd_get(self, bot, update, args):
        """
        Sends all the stickers of linked with a tag. For debug purposes mainly.

        :param args: Tags linked with the stickers.
        """
        try:
            tg_msg = update.message
            tg_chat = update.effective_chat
            tg_user = update.effective_user
            tg_user_id = str(tg_user.id)
            tg_username = tg_user.username
            if tg_chat.type != 'private':
                tg_msg.reply_text("Sorry, this command only works in private chats.")
                raise WrongContextError(
                    err_message="Command /get called by user " + tg_username + " raised an exception.",
                    err_cause="Chat type is " + tg_chat.type + ".")
            if len(args) == 0:
                tg_msg.reply_text("You need to give me at least 1 tag to search for stickers.")
                raise InputError(err_message="Command /get called by user " + tg_username + " raised an exception.",
                                 err_cause="Not enough arguments.")
            sf_user = self.user_db.get_item(tg_user_id) if tg_user_id in self.user_db \
                else self.user_db.get_item('SF-PUBLIC')
            
            sticker_list = self._get_sticker_list(sf_user, args, sf_user.id)
            for file_id in sticker_list:
                try:
                    bot.send_sticker(chat_id=tg_chat.id, sticker=file_id)
                except TelegramError:
                    self._delete_from(update, tg_user, args, file_id)
            self._logger.info("Sent stickers tagged with " + ", ".join(args) + " to %s.", tg_username)
        except WrongContextError as e:
            self._log_error(e)
        except InputError as e:
            self._log_error(e)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /get command with "
                                       "parameters: " + ", ".join(args) + ".")

    def cmd_get_db(self, bot, update):
        """Sends a copy of the database via chat."""
        try:
            tg_msg = update.message
            tg_user = update.effective_user
            if tg_user.id not in self._admins:
                tg_msg.reply_text("You have no permission to use this command. Please contact an admin.")
                raise InsufficientPermissionsError(
                    err_message="Command /getDB called by user " + str(tg_user.username) + " raised an exception.",
                    err_cause="User " + str(tg_user.username) + " is not an admin.")
            bot.send_document(chat_id=tg_user.id, document=open("stickfix-user-DB.dat", 'rb'))
            bot.send_document(chat_id=tg_user.id, document=open("stickfix-user-DB.dir", 'rb'))
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /getDB command.")
            
    def cmd_help(self, bot, update):
        """Sends a message with help to the user."""
        try:
            bot.send_message(
                chat_id=update.effective_chat.id,
                text=HELP_MESSAGE[0],
                parse_mode=ParseMode.MARKDOWN)
            bot.send_message(
                chat_id=update.effective_chat.id,
                text=HELP_MESSAGE[1],
                parse_mode=ParseMode.MARKDOWN
            )
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /help command.")

    def cmd_restore(self, bot, update, args):
        """
        Restores the database to a previous version.
        
        :param args:
            ID of the backup that wants to be restored.
        """
        try:
            tg_msg = update.message
            tg_user = update.effective_user
            if tg_user.id not in self._admins:
                tg_msg.reply_text("You have no permission to use this command. Please contact an admin.")
                raise InsufficientPermissionsError(
                    err_message="Command /restore called by user " + str(tg_user.username) + " raised an exception.",
                    err_cause="User " + str(tg_user.username) + " is not an admin.")
            n = len(args)
            if n > 1:
                tg_msg.reply_text("This command can't take more than 1 parameter")
                raise InputError(
                    err_message="Command /restore called by user " + tg_user.username + " raised an exception.",
                    err_cause="Too many arguments.")
            if n == 0:
                self._restore_from_backup()
            else:
                self._restore_from_backup(int(args[0]))
            tg_msg.reply_text("Ok.")
        except InsufficientPermissionsError as e:
            self._notify_error(bot, e, e.message, e.cause)
        except InputError as e:
            self._log_error(e)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /deleteMe command.")

    def cmd_set_mode(self, bot, update, args):
        """
        Changes the user mode to `PUBLIC` or `PRIVATE`.
        By default all users are in `PUBLIC` mode.
        
        :param args:
             Desired mode. Can be `public` or `private`. Ignores case.
        """
        try:
            tg_user = update.effective_user
            if len(args) != 1:
                update.message.reply_text(
                    "Sorry, this command only accepts 1 parameter. Send <code>/setMode private</code> or "
                    "<code>/setMode public</code>.",
                    parse_mode=ParseMode.HTML)
                raise InputError(
                    err_message="Command /setMode called by user " + tg_user.username + " raised an exception.",
                    err_cause="Wrong number of arguments.")
            tg_user_id = str(tg_user.id)
            # Se crea el usuario si no está en la BDD.
            if tg_user_id not in self.user_db:
                self._logger.info("User %s was added to the database", tg_user.username)
                self._create_user(tg_user_id)

            user = self.user_db.get_item(tg_user_id)
            if args[0].upper() == 'PRIVATE':
                user.private_mode = StickfixUser.ON
                self._logger.info("User %s changed to private mode", tg_user.username)
            elif args[0].upper() == 'PUBLIC':
                user.private_mode = StickfixUser.OFF
                self._logger.info("User %s changed to public mode", tg_user.username)
            else:
                update.message.reply_text(
                    "Sorry, I didn't understand. Send <code>/setMode private</code> or <code>/setMode public</code>.",
                    parse_mode=ParseMode.HTML)
                raise InputError(
                    err_cause=args[0] + " is not a valid argument.",
                    err_message="Command /setMode called by user " + tg_user.username + " raised an exception.")
            self.user_db.add_item(user.id, user)
            update.message.reply_text("Ok.")
        except InputError as e:
            self._log_error(e)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /setMode command with "
                                       "parameters: " + ", ".join(args) + ".")

    def cmd_set_shuffle(self, bot, update, args):
        """
        Turns on or off the shuffle mode.
        By default shuffle is off.
        
        :param args:
            Desired mode. Can be `on` or `off`
        """
        try:
            tg_user = update.effective_user
            if len(args) != 1:
                update.message.reply_text(
                    "Sorry, this command only accepts 1 parameter. Send <code>/shuffle on</code> or <code>/shuffle "
                    "off</code>.",
                    parse_mode=ParseMode.HTML)
                raise InputError(
                    err_message="Command /shuffle called by user " + tg_user.username + " raised an exception.",
                    err_cause="Wrong number of arguments.")
            tg_user_id = str(tg_user.id)
            # Se crea el usuario si no está en la BDD.
            if tg_user_id not in self.user_db:
                self._logger.info("User %s was added to the database", tg_user.username)
                self._create_user(tg_user_id)

            user = self.user_db.get_item(tg_user_id)
            if args[0].upper() == 'ON':
                user._shuffle = StickfixUser.ON
                self._logger.info("User %s turned on the shuffle mode", tg_user.username)
            elif args[0].upper() == 'OFF':
                user._shuffle = StickfixUser.OFF
                self._logger.info("User %s turned off the shuffle mode", tg_user.username)
            else:
                update.message.reply_text(
                    "Sorry, I didn't understand. Send <code>/shuffle on</code> or <code>/shuffle off</code>.",
                    parse_mode=ParseMode.HTML)
                raise InputError(
                    err_cause=args[0] + " is not a valid argument.",
                    err_message="Command /shuffle called by user " + tg_user.username + " raised an exception.")
            self.user_db.add_item(user.id, user)
            update.message.reply_text("Ok.")
        except InputError as e:
            self._log_error(e)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /setMode command with "
                                       "parameters: " + ", ".join(args) + ".")

    def cmd_start(self, bot, update):
        """Greets the user."""
        try:
            tg_user = update.effective_user
            tg_user_id = str(tg_user.id)
            update.message.reply_sticker('CAADBAADTAADqAABTgXzVqN6dJUIXwI')
            if tg_user_id not in self.user_db:
                # TODO -cAdd -v2.2 : Se debería preguntar al usuario si desea ser añadido a la BDD  —Ignacio.
                self._logger.info("User %s was added to the database", tg_user.username)
                self._create_user(tg_user_id)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured while calling the /start command.")
    
    # endregion

    # region Inline queries
    def _inline_get(self, bot, update):
        """Gets all the stickers linked with a list of tags and sends them as an inline query answer."""
        try:
            tg_inline = update.inline_query
            tg_query = tg_inline.query
            tg_user_id = str(update.effective_user.id)
            sf_user = self.user_db.get_item(tg_user_id) if tg_user_id in self.user_db \
                else self.user_db.get_item('SF-PUBLIC')
            
            offset = 0 if not tg_inline.offset else int(tg_inline.offset)
            tags = str(tg_query).split(" ")
            
            results = []
            if offset == 0:
                sf_user.remove_cached_stickers(tg_user_id)
                if not tg_query:
                    if sf_user.private_mode == StickfixUser.ON:
                        tags = sf_user.random_tag()
                    else:
                        tags = self.user_db.get_item('SF-PUBLIC').random_tag()
                    display_title = "Showing stickers in: " + tags[0] if len(tags) != 0 \
                        else "I have no stickers to show you, try adding your own"
                    results.append(
                        InlineQueryResultArticle(
                            id=uuid4(), title=display_title,
                            description="Click this if you want me to send a message to this chat with help.",
                            input_message_content=InputTextMessageContent("\n\n".join(HELP_MESSAGE),
                                                                          parse_mode=ParseMode.MARKDOWN)))
            
            # noinspection PyProtectedMember
            sticker_list = self._get_sticker_list(sf_user, tags, tg_user_id, sf_user._shuffle)

            upper_bound = min(len(sticker_list), offset + 49)
            for i in range(offset, upper_bound):
                results.append(InlineQueryResultCachedSticker(id=uuid4(), sticker_file_id=sticker_list[i]))
            try:
                bot.answer_inline_query(tg_inline.id, results, cache_time=1, is_personal=True,
                                        next_offset=str(offset + 49))
            except TelegramError as e:
                self._notify_error(bot, e,
                                   "An exception occured while trying to get inline results with tags: <code> " +
                                   " ".join(tags) + "</code>")
            self.user_db.add_item(sf_user.id, sf_user)
        except Exception as e:
            self._notify_error(bot, e,
                               "An unexpected exception occured while calling inline mode with query: <code>" +
                               update.inline_query.query + "</code>.")

    def _on_inline_result(self, bot, update):
        try:
            tg_user_id = str(update.effective_user.id)
            sf_user = self.user_db.get_item(tg_user_id)
            if not sf_user:
                sf_user = self.user_db.get_item('SF-PUBLIC')
            sf_user.remove_cached_stickers(tg_user_id)
            self.user_db.add_item(sf_user.id, sf_user)
            self._logger.info("Answered inline query for %s.", update.chosen_inline_result.query)
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "An unexpected exception occured on chosen inline result.")
    
    # endregion

    # region Job queue callbacks
    def periodic_backup(self, bot, job):
        """Creates a backup of the database periodically."""
        try:
            copyfile(src="stickfix-user-DB.dat", dst="stickfix-user-DB-bk" + str(self._current_backup_id) + ".dat")
            copyfile(src="stickfix-user-DB.dir", dst="stickfix-user-DB-bk" + str(self._current_backup_id) + ".dir")
            self._logger.info("Created backup file stickfix-user-DB-bk" + str(self._current_backup_id))
            self._current_backup_id = (self._current_backup_id + 1) % 2
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "There was an unexpected error while trying to make the periodic backup.")

    def periodic_cache_remove(self, bot, job):
        """Periodically clears the cache."""
        try:
            for user_id in self.user_db.get_keys():
                user = self.user_db.get_item(user_id)
                user.cached_stickers = {}
                self.user_db.add_item(user_id, user)
        except Exception as e:
            self._notify_error(bot, e, "There was an unexpected error while trying to do periodic cache removal.")

    def periodic_database_check(self, bot, job):
        """Checks for database integrity."""
        try:
            if self.user_db.is_empty() and not self._empty_db:
                last_backup = str((self._current_backup_id - 1) % 2)

                copyfile(src="stickfix-user-DB-bk" + last_backup + ".dat", dst="stickfix-user-DB.dat")
                copyfile(src="stickfix-user-DB-bk" + last_backup + ".dir", dst="stickfix-user-DB.dir")
                self._logger.info("Database was restored to last backup.")
            self._empty_db = False
        except TelegramError as e:
            raise e
        except Exception as e:
            self._notify_error(bot, e, "There was an unexpected error during automatic database check.")

    # endregion
    
    def _contact_admins(self, bot, message):
        """Sends a message to all admin users."""
        for admin_id in self._admins:
            bot.send_message(chat_id=admin_id, text=message, parse_mode=ParseMode.HTML)

    def _delete_from(self, update, tg_user, args, sticker_id=None):
        tg_user_id = str(tg_user.id)
        sf_user = self.user_db.get_item(tg_user_id) if tg_user_id in self.user_db else None
        if sf_user is None or sf_user.private_mode == StickfixUser.OFF:
            # Si el usuario no existe o está en modo público, se considera el usuario como `SF-PUBLIC`
            sf_user = self.user_db.get_item('SF-PUBLIC')
        sticker_id = update.effective_message.reply_to_message.sticker.file_id if sticker_id is None else sticker_id
        sf_user.remove_sticker(sticker_id=sticker_id, sticker_tags=args)
        self.user_db.add_item(sf_user.id, sf_user)
        self._logger.info("Sticker deleted from %s's pack with tags: " + ', '.join(args), tg_user.username)
    
    def _create_user(self, user_id):
        """
        Creates a new `StickfixUser` and adds it to the database.

        :param user_id:
            ID of the user to be created.
        """
        user = StickfixUser(user_id)
        self.user_db.add_item(user_id, user)
        return user
    
    def _error_callback(self, bot, update, error):
        """Log errors."""
        try:
            raise error
        except Unauthorized as e:
            self._logger.error(e.message + ". " + " | ".join(e.args))
        except BadRequest as e:
            self._logger.error(e.message + ". " + " | ".join(e.args))
        except TimedOut as e:
            self._logger.error(e.message + ". " + " | ".join(e.args))
        except NetworkError as e:
            self._logger.error(e.message + ". " + " | ".join(e.args))
        except ChatMigrated as e:
            self._logger.error(e.message + ". " + " | ".join(e.args))
        except TelegramError as e:
            self._logger.error(e.message + ". " + " | ".join(e.args))

    def _get_sticker_list(self, sf_user, tags, user_id, shuffle=False):
        """
        Gets all the stickers from a user that mathces the given tags.
        
        :return:
            A list containing all the stickers that matches the tags.
        """
        # Hay que pensar si hay alguna manera menos redundante de implementar esto -Ignacio.
        str_tags = '-'.join(tags)
        if user_id in sf_user.cached_stickers:
            if str_tags == '':
                return list(sf_user.cached_stickers[user_id].values())[0]
            return sf_user.cached_stickers[user_id][str_tags]
        stickers = []
        if len(tags) == 0:
            return stickers
        for tag in tags:
            match = set()
            if sf_user.private_mode == StickfixUser.OFF:
                match = self.user_db.get_item('SF-PUBLIC').get_stickers(sticker_tag=tag)
            stickers.append(match.union(sf_user.get_stickers(sticker_tag=tag)))
        sticker_list = list(set.intersection(*stickers))
        if shuffle:
            random.shuffle(sticker_list)
        sf_user.cached_stickers[user_id] = {str_tags: sticker_list}
        return sticker_list

    def _log_error(self, error, context=None):
        """Logs an error."""
        log = error.__class__.__name__ + ": " + error.message + " Cause: " + error.cause
        if context is not None:
            log += " Context: " + str(context)
        self._logger.error(log)

    def _notify_error(self, bot, error, message, cause=None):
        """Logs and notifies admins about errors."""
        if cause is None:
            cause = " | ".join(error.args)
        self._contact_admins(bot, message + " | " + cause + " | Details: \n <code>" + format_exc() + "</code>")
        self._logger.error(
            message + "\n Type: " + error.__class__.__name__ + "\n Details: " + cause + "\n Trace: " + format_exc())
    
    def _restore_from_backup(self, backup_id=None):
        """
        Restores the database to the indicated backup.
        
        :param backup_id:
            ID of the backup that wants to be restored.
            If no ID is given, restores to the last backup.
        """
        try:
            if backup_id is None:
                backup_id = (self._current_backup_id - 1) % 2
            backup_id = str(backup_id)

            copyfile(src="stickfix-user-DB-bk" + backup_id + ".dat", dst="stickfix-user-DB.dat")
            copyfile(src="stickfix-user-DB-bk" + backup_id + ".dir", dst="stickfix-user-DB.dir")
            self._logger.info("Database was restored to backup %s.", backup_id)
        except OSError as e:
            self._logger.error(e.strerror)
        except Exception as e:
            self._logger.error(str(e.__class__.__name__) + ": " + ' | '.join(e.args))
