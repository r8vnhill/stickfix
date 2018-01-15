#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from telegram import ParseMode
from telegram.error import BadRequest, ChatMigrated, NetworkError, TelegramError, TimedOut, Unauthorized
from telegram.ext import CommandHandler, Updater

from sf_user import StickfixUser
from shelve_db import ShelveDB

__author__ = "Ignacio Slater Muñoz"
__email__ = "ignacio.slater@ug.uchile.cl"
__version__ = "1.1.1"


class StickfixBot:
    """
    Base class for @stickfixbot.
    This class implements functions to help manage and store stickers in
    telegram using chat commands and inline queries.
    """

    def __init__(self, token):
        """
        Initializes the bot.

        :param token:
            Bot's TOKEN.
        """
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
        self._user_db = ShelveDB("stickfix-user-DB")
        self._logger = logging.getLogger(__name__)
        self._updater = Updater(token)
        self._dispatcher = self._updater.dispatcher

        self._dispatcher.add_handler(CommandHandler("start", self._start))
        self._dispatcher.add_handler(CommandHandler("help", self._help))
        self._dispatcher.add_handler(CommandHandler("deleteMe", self._delete_user))
        self._dispatcher.add_handler(CommandHandler("setMode", self._set_mode, pass_args=True))
        self._dispatcher.add_handler(CommandHandler("add", self._add, pass_args=True))
        self._dispatcher.add_handler(CommandHandler('get', self._get_all, pass_args=True))
        # TODO -cFeature -v1.2 : Implementar inline query para enviar stickers -Ignacio.
        # TODO -cFeature -v1.3 : Implementar comandos para manejar la BDD -Ignacio.
        # TODO -cFeature -v2.1: Implementar comando addSet.
        # Revisar http://python-telegram-bot.readthedocs.io/en/stable/telegram.html `get_sticker_set` -Ignacio.

        self._dispatcher.add_error_handler(self._error_callback)  # Para logging de errores.

    def run(self):
        """
        Starts the bot.
        """
        self._updater.start_polling()

    def _create_user(self, user_id):
        """
        Creates a new `StickfixUser` and adds it to the database.
        
        :param user_id:
            ID of the user to be created.
        """
        user = StickfixUser(user_id)
        self._user_db.add_item(user_id, user)

    def _error_callback(self, bot, update, error):
        """Log errors."""
        try:
            raise error
        except Unauthorized as e:
            self._logger.error(e.message)
        except BadRequest as e:
            self._logger.error(e.message)
        except TimedOut as e:
            self._logger.error(e.message)
        except NetworkError as e:
            self._logger.error(e.message)
        except ChatMigrated as e:
            self._logger.error(e.message)
        except TelegramError as e:
            self._logger.error(e.message)

    # region Chat commands
    def _add(self, bot, update, args):
        """
        Adds a sticker to the database.
        
        :param args:
            Tags that identify the pack to which the stickers are going to be added.
        """
        tg_reply_to = update.effective_message.reply_to_message
        tg_msg = update.message
        tg_user = update.effective_user
        tg_user_id = str(tg_user.id)
        if tg_reply_to is None:  # Si no se responde a ningún mensaje.
            tg_msg.reply_text(
                "To add a sticker to the database, you need to *reply to a message* containing the sticker you want "
                "to add.",
                parse_mode=ParseMode.MARKDOWN)
        else:
            tg_sticker = tg_reply_to.sticker
            if tg_sticker is None:  # Si el mensaje al que se responde no contiene ningún sticker.
                tg_msg.reply_text("I can only add stickers to de database.")
            else:
                if len(args) == 0:  # Si no se especifica un tag, se toma el emoji asociado al sticker.
                    tags = [tg_sticker.emoji]
                else:
                    tags = args
            
                if tg_user_id not in self._user_db:  # Si el usuario no está en la BDD se toma como GUEST.
                    tg_user_id = 'GUEST'
                if 'GUEST' not in self._user_db:  # Se crea el usuario GUEST si no existe.
                    self._create_user('GUEST')
                    self._logger.info('Created GUEST user.')
            
                if self._user_db.get_item(tg_user_id).mode == StickfixUser.PRIVATE:
                    sf_user = self._user_db.get_item(tg_user_id)
                    tg_username = tg_user.username
                else:
                    sf_user = self._user_db.get_item('GUEST')
                    tg_username = 'stickfix-public'
            
                sf_user.add_sticker(sticker_id=tg_sticker.file_id, sticker_tags=tags)
                self._user_db.add_item(sf_user.id, sf_user)
                self._logger.info("Sticker added to %s's pack with tags: " + ', '.join(tags), tg_username)

    def _delete_user(self, bot, update):
        """Deletes the user who sent the command from the database."""
        tg_user = update.effective_user
        tg_user_id = str(tg_user.id)
        # TODO -cFeature -v2.1 : Pedir confirmación al usuario -Ignacio.
        if tg_user_id in self._user_db:
            self._user_db.delete_by_key(tg_user_id)
            self._logger.info("User %s was removed from the database", tg_user.username)
            update.message.reply_text("Ok.")
        else:
            update.message.reply_text("You're not in my database.")

    def _get_all(self, bot, update, args):
        """
        Sends all the stickers of linked with a tag. For debug purposes mainly.

        :param args: Tags linked with the stickers.
        """
        tg_msg = update.message
        tg_chat = update.effective_chat
        if tg_chat.type != 'private':
            tg_msg.reply_text("Sorry, this command only works in private chats.")
        elif len(args) == 0:
            tg_msg.reply_text("You need to give me at least 1 tag to search for stickers.")
        else:
            # Hay que pensar si hay alguna manera menos redundante de implementar esto -Ignacio.
            tg_user_id = str(update.effective_user.id)
            if tg_user_id not in self._user_db:
                tg_user_id = 'GUEST'
            sf_user = self._user_db.get_item(tg_user_id)
    
            stickers = []
            for tag in args:
                match = set()
                if sf_user.mode == StickfixUser.PUBLIC:
                    match = self._user_db.get_item('GUEST').get_stickers(sticker_tag=tag)
                stickers.append(match.union(sf_user.get_stickers(sticker_tag=tag)))
            sticker_list = list(set.intersection(*stickers))
    
            for file_id in sticker_list:
                bot.send_sticker(chat_id=tg_chat.id, sticker=file_id)
        self._logger.info("Sent stickers tagged with " + ", ".join(args) + " to %s.", update.effective_user.username)

    def _help(self, bot, update):
        """Sends a message with help to the user."""
        # TODO -cFeature -v2.0 : Actualizar ayuda de acuerdo a la nueva versión -Ignacio.
        update.message.reply_text(
            "Yo! I'm StickFix, I can link keywords with stickers so you can "
            'manage them more easily. '
            'By default, all tags are global (everyone can access them), but '
            'you can also create your own _personal collection_ of tags.\n'

            'You can control me by sending me these commands:\n'
            '/tags \[p] - _Sends a message with all the tags that have '
            'stickers_\n'
            '/add \[p] <tag> - _Links a sticker with a tag, where <tag> is a '
            'hashtag. For this to work you have to reply to a message that '
            'contains a sticker with the command; I need access to the '
            'messages to do this._\n'
            '/deleteFrom \[p] <tag> - _Works like /add, it deletes a sticker '
            'from a tag._\n'
            '\n'
            '*In private:*\n'
            '/get \[p] <tag> - _Sends all stickers tagged with <tag>._\n'
            'Where \[p] is an optional parameter that indicates if the sticker '
            'is going to be added to (or retrieved from) a personal collection.'
            ' For example, if you send me `/add p #tag` I will store the '
            'sticker you signaled me to your personal collection.\n'
            '\n'
            'You can also call me inline like `@stickfixbot [p] [r] #tag` to '
            'see a list of all the stickers you have tagged with #tag, where '
            '\[p] is the same as before, and \[r] indicates that you want to '
            'get a random sticker from the #tag, both parameters are optional.',
            parse_mode=ParseMode.MARKDOWN
        )

    def _set_mode(self, bot, update, args):
        """
        Changes the user mode to `PUBLIC` or `PRIVATE`.
        By default all users are in `PUBLIC` mode.
        
        :param args:
             Desired mode. Can be `public` or `private`. Ignores case.
        """
        if len(args) != 1:
            update.message.reply_text(
                "Sorry, this command only accepts 1 parameter. Send `/setMode private` or `/setMode public`.",
                parse_mode=ParseMode.MARKDOWN)
        else:
            tg_user = update.effective_user
            tg_user_id = str(tg_user.id)
            # Se crea el usuario si no está en la BDD.
            if tg_user_id not in self._user_db:
                self._logger.info("User %s was added to the database", tg_user.username)
                self._create_user(tg_user_id)
    
            user = self._user_db.get_item(tg_user_id)
            if args[0].upper() == 'PRIVATE':
                user.mode = StickfixUser.PRIVATE
                self._logger.info("User %s changed to private mode", tg_user.username)
            elif args[0].upper() == 'PUBLIC':
                user.mode = StickfixUser.PUBLIC
                self._logger.info("User %s changed to public mode", tg_user.username)
            self._user_db.add_item(user.id, user)
            update.message.reply_text("Ok.")

    def _start(self, bot, update):
        """Greets the user."""
        tg_user = update.effective_user
        tg_user_id = str(tg_user.id)
        update.message.reply_sticker('CAADBAADTAADqAABTgXzVqN6dJUIXwI')
        if tg_user_id not in self._user_db:
            # TODO -cFeature -v2.1 : Se debería preguntar al usuario si desea ser añadido a la BDD -Ignacio.
            self._logger.info("User %s was added to the database", tg_user.username)
            self._create_user(tg_user_id)
    # endregion
