#!/usr/bin/env python
import random
import re
import threading
import time

import telepot
from telepot.helper import Answerer
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineQueryResultCachedSticker

from shelve_db import ShelveDB

__author__ = "Ignacio Slater Muñoz"
__email__ = "ignacio.slater@ug.uchile.cl"


def on_chosen_inline_result(msg):
    result_id, from_id, query_string = telepot.glance(
        msg, flavor='chosen_inline_result')
    print('Chosen Inline Result:', result_id, from_id, query_string)


def is_valid(tag):
    return re.fullmatch("#[A-Za-z][\w_]*", tag) is not None


class StickerHelperBot:
    """
    Este bot implementa algunas funcionalidades para usar stickers de telegram.
    CLIENT class.
    """

    def __init__(self, token, admins=None):
        """
        Define los valores iniciales del bot.

        :param token:  TOKEN del bot.
        :param admins: ID de los usuarios que tienen privilegio de administrador
                       para el bot. Necesario para manejar elementos internos
                       del bot, como reestablecer la base de datos y manejar
                       copias de seguridad.
        """
        self._msg = None

        self._db = ShelveDB("stickerDB")
        self._admins = [] if (admins is None) else admins

        self._bot = telepot.Bot(token)
        self._answerer = InlineHandler(self._bot)
        self._id = self._bot.getMe()['id']
        # Comandos
        self._chat_cmd = {
            "/start": self.greet,
            "/backup": self.backup_db,
            "/help": self.help,
            "/tags": self.show_tags,
            "/resetDB": self.reset_db,
            "/add": self.add,
            "/deleteFrom": self.delete_from_tag,
            "/deleteTags": self.delete_tag,
            "/get": self.get_all
        }

    def run(self):
        """Corre el bot."""
        MessageLoop(self._bot, {'chat': self.chat_handle,
                                'inline_query': self.inline_handle,
                                'chosen_inline_result': on_chosen_inline_result}
                    ).run_as_thread()
        print('Listening ...')

        while True:
            time.sleep(10)

    # Comandos normales
    def chat_handle(self, msg):
        """
        Handle de los mensajes recibidos por chat.

        :param msg: Mensaje.
        """
        self._msg = msg
        content_type, chat_type, chat_id = telepot.glance(msg)
        print(content_type, chat_type, chat_id)
        # Si comienza un chat.
        if content_type == 'new_chat_member':
            if msg['new_chat_member']['id'] == self._id:
                self.greet(chat_id)
        if not content_type == 'text':  # Ignora los mensajes que no sean texto
            return
        text = msg['text']
        self.exec_command(text, chat_id, chat_type)

    def exec_command(self, msg, chat_id, chat_type):
        """
        Ejecuta un comando.

        :param msg:       Texto del mensaje.
        :param chat_id:   ID del chat desde el que se llama al comando.
        :param chat_type: Tipo del chat desde el que se llama al comando.
        """
        msg = msg.split(" ")
        cmd = msg[0]
        params = msg[1:] if len(msg) > 1 else None

        if cmd in self._chat_cmd:
            self._chat_cmd[cmd](chat_id, chat_type, params)

    def add(self, chat_id, chat_type, params):
        """
        Asocia un sticker con un tag.
        Si el tag no existe, se crea; si el sticker ya está relacionado con el
        tag, se ignora.

        :param chat_id:   No utilizado.
        :param chat_type: No utilizado.
        :param params:    Parámetros que recibe el comando.
        """
        try:
            if params is not None:
                user_id = ''
                i = 0
                if params[i] == 'p':
                    user_id = str(self._msg['from']['id']) + ":"
                    i += 1
                reply = self._msg['reply_to_message']
                reply_type = telepot.glance(reply)[0]

                if reply_type == 'sticker':
                    tags = params[i:]
                    sticker = reply['sticker']['file_id']
                    for tag in tags:
                        if not is_valid(tag):
                            continue
                        result = self._db.add_item(user_id + tag, sticker)
                        if result:
                            print("Added sticker to " + tag)
                        else:
                            print("Sticker was already stored")
        except KeyError as e:
            print(e)

    def delete_from_tag(self, chat_id, chat_type, params):
        """
        Elimina un sticker de un tag.

        :param chat_id:   Id del chat del que se llama al comando.
        :param chat_type: No utilizado.
        :param params:    Parámetros que se le entregan al comando.
        """
        if params is not None:
            user_id = ''
            i = 0
            if params[i] == 'p':
                user_id = str(self._msg['from']['id']) + ":"
                i = 1
            tags = params[i:]
            sticker_id = self._msg['reply_to_message']['sticker']['file_id']
            for tag in tags:
                try:
                    self._db.delete_from_key(user_id + tag, sticker_id)
                    self._bot.sendMessage(
                        chat_id,
                        "Sticker successfully deleted from " + tag + ".")
                except KeyError as e:
                    self._bot.sendMessage(
                        chat_id,
                        "Couldn't find the sticker in " + tag + ".")
                    print(e)

    def delete_tag(self, chat_id, chat_type, params):
        """
        Elimina un tag de la base de datos.

        :param chat_id:   Id del chat desde el que se llama al comando.
        :param chat_type: No utilizado.
        :param params:    Parámetros que se le entregan al comando.
        """
        if chat_id in self._admins:
            for tag in params:
                if self._db.delete_by_key(tag):
                    self._bot.sendMessage(
                        chat_id,
                        "Tag " + tag + " was deleted successfully.")
                else:
                    self._bot.sendMessage(chat_id,
                                          "The tag " + tag + " doesn't exist.")
        else:
            self._bot.sendMessage(
                chat_id,
                "You have no power over me. Please contact an admin.")

    def get_all(self, chat_id, chat_type, params):
        """
        Envía todos los stickers que pertenezcan a los tags especificados.

        :param chat_id:
        :param chat_type:
        :param params:
        :return:
        """
        if chat_type == 'private' and params is not None:
            i = 1 if params[0] == 'p' else 0
            stickers = self.get_stickers(chat_id, params[i:], bool(i))
            if len(stickers) == 0:
                self._bot.sendMessage(chat_id, "Nothing to get.")
                return

            for item in stickers:
                self._bot.sendSticker(chat_id, item)

    def show_tags(self, chat_id, chat_type, params):
        """
        Envía un mensaje conteniendo todos los tags almacenados.

        :param chat_id:   Id del chat desde el que se llama al comando.
        :param params:    Parámetros que recibe el comando. 'p' indica que se
                          mostrarán los tags personales.
        :param chat_type: No utilizado.
        """
        ignore_params = False
        tags = []
        if params is not None:
            if params[0] == 'p':
                for tag in self._db.get_keys():
                    if tag.startswith(str(self._msg['from']['id']) + ':'):
                        tags.append(tag.split(':')[1] + " (" + str(
                            len(self._db.get_item(tag))) + ")")
            else:
                ignore_params = True
        if params is None or ignore_params:
            for tag in self._db.get_keys():
                if is_valid(tag):
                    tags.append(
                        tag + " (" + str(len(self._db.get_item(tag))) + ")")

        if len(tags) == 0:
            self._bot.sendMessage(chat_id, "No tags here.")
            return

        tags.sort()
        message = '\n'.join(tags)
        self._bot.sendMessage(chat_id, message)

    def reset_db(self, chat_id, chat_type=None, params=None):
        """
        Reestablece la base de datos completa.
        Para llamar a este comando, se deben tener privilegios de administrador.

        :param params:    No utilizado.
        :param chat_type: No utilizado.
        :param chat_id:   ID del usuario que invoca el comando.
        """
        if chat_id in self._admins:
            self._bot.sendMessage(chat_id, "Wait a moment...")
            self.backup_db(chat_id)
            self._db.reset()
            self._bot.sendMessage(chat_id, "Database emptied.")
        else:
            self._bot.sendMessage(
                chat_id,
                "You have no power over me. Please contact an admin.")

    def backup_db(self, chat_id, chat_type=None, params=None):
        """
        Envía una copia de seguridad de la base de datos.

        :param chat_id:   ID del chat desde el que se llama al comando.
        :param chat_type: No utilizado.
        :param params:    No utilizado.
        """
        if chat_id in self._admins:
            db = open("stickerDB.bak")
            from datetime import datetime
            date = datetime.now().strftime("%c")
            for admin in self._admins:
                self._bot.sendDocument(admin, db, date)

    # Inline
    def inline_handle(self, msg):
        self._msg = msg
        self._answerer.answer(msg, self.compute)

    def compute(self):
        stickers = []
        query_id, from_id, query_string = telepot.glance(self._msg,
                                                         flavor='inline_query')
        print('%s: Computing for: %s' % (
            threading.current_thread().name, query_string))
        cmd = query_string.split(" ")
        i = 0
        is_personal, is_random = False, False
        if len(cmd) > 1:
            if (cmd[0] == 'p' or cmd[1] == 'p') and not is_valid(cmd[0]):
                is_personal = True
                i += 1
            if (cmd[0] == 'r' or cmd[1] == 'r') and not is_valid(cmd[0]):
                is_random = True
                i += 1
        items = self.get_stickers(from_id, cmd[i:], is_personal, is_random)

        if len(items) >= 50:
            items = random.sample(items, 50)
            items.sort()
        for item in items:
            stickers.append(InlineQueryResultCachedSticker(
                type="sticker",
                id=item,
                sticker_file_id=item
            ))
        return stickers

    # Helper methods
    def get_stickers(self, user_id, tags, is_personal=False, is_random=False):
        stickers = []
        if is_personal:
            for tag in tags:
                stickers.append(
                    set(self._db.get_item(str(user_id) + ":" + tag)))
        else:
            for tag in tags:
                stickers.append(
                    set(self._db.get_item(str(user_id) + ":" + tag)) |
                    set(self._db.get_item(tag)))

        if len(stickers) > 0:
            stickers = list(set.intersection(*stickers))
            if is_random:
                stickers = [random.choice(stickers)]
            else:
                stickers.sort()
        return stickers

    def greet(self, chat_id, chat_type=None, params=None):
        """
        Envía un saludo.

        :param chat_id:   ID del chat.
        :param chat_type: No utilizado.
        :param params:    No utilizado.
        """
        self._bot.sendSticker(
            chat_id,
            'CAADBAADTAADqAABTgXzVqN6dJUIXwI')  # file_id del fogs helo
        self._bot.sendMessage(chat_id, "Can I /help you?")

    def help(self, chat_id, chat_type=None, params=None):
        self._bot.sendMessage(
            chat_id,
            "Yo! I'm StickFix, I can link keywords with stickers so you can "
            'manage them more easily.\n'

            'You can control me by sending me these commands:\n'
            '/tags - _Sends a message with all the tags that have stickers_\n'
            '/add <tag> - _Links a sticker with a tag, where <tag> is a '
            'hashtag. For this to work you have to reply to a message that '
            'contains a sticker with the command; I need access to the '
            'messages to do this._\n'
            '/pickRandom <tag> - _Sends a random sticker tagged with <tag>._\n'
            '/deleteFrom <tag> - _Works like /add, it unlinks a sticker from '
            'a tag._\n'
            '\n'
            '*In private:*\n'
            '/get <tag> - _Sends all stickers tagged with <tag>._\n'
            '\n'
            'You can also call me inline like `@stickfixbot #tag` to see a '
            'list of all the stickers you have tagged with #tag.',
            parse_mode="Markdown")


class InlineHandler(Answerer):
    def __init__(self, bot):
        super().__init__(bot)

    def answer(self, inline_query, compute_fn, *compute_args, **compute_kwargs):
        """
        This is a modification of telepot.helper.Answerer
        """

        from_id = inline_query['from']['id']

        class Worker(threading.Thread):
            def __init__(self, bot, lock, workers):
                super(Worker, self).__init__()
                self._bot = bot
                self._lock = lock
                self._workers = workers
                self._cancelled = False

            def cancel(self):
                self._cancelled = True

            def run(self):
                try:
                    query_id = inline_query['id']

                    if self._cancelled:
                        return

                    # Important: compute function must be thread-safe.
                    ans = compute_fn(*compute_args, **compute_kwargs)

                    if self._cancelled:
                        return

                    if isinstance(ans, list):
                        self._bot.answerInlineQuery(query_id, ans, cache_time=0,
                                                    is_personal=True)
                    elif isinstance(ans, tuple):
                        self._bot.answerInlineQuery(query_id, *ans,
                                                    cache_time=0,
                                                    is_personal=True)
                    elif isinstance(ans, dict):
                        self._bot.answerInlineQuery(query_id, **ans,
                                                    cache_time=0,
                                                    is_personal=True)
                    else:
                        raise ValueError('Invalid answer format')
                finally:
                    with self._lock:
                        # Delete only if I have NOT been cancelled.
                        if not self._cancelled:
                            del self._workers[from_id]

                            # If I have been cancelled, that position in
                            # `outerself._workers` no longer belongs to me. I
                            #  should not delete that key.

        # Several threads may access `outerself._workers`. Use
        # `outerself._lock` to protect.
        with self._lock:
            if from_id in self._workers:
                self._workers[from_id].cancel()

            self._workers[from_id] = Worker(self._bot, self._lock,
                                            self._workers)
            self._workers[from_id].start()
