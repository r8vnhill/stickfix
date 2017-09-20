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
    result_id, from_id, query_string = telepot.glance(msg, flavor='chosen_inline_result')
    print('Chosen Inline Result:', result_id, from_id, query_string)


def is_valid(tag):
    return re.fullmatch("#[A-Za-z][\w_]*", tag) is not None


# TODO: refactor, varios parámetros, multitag
class StickerHelperBot:
    """Este bot implementa algunas funcionalidades para usar stickers de telegram."""

    def __init__(self, token, admins=None):
        """
        Define los valores iniciales del bot.

        :param token:   TOKEN del bot.
        :param admins:  ID de los usuarios que tienen privilegio de administrador para el bot. Necesario para manejar
                        elementos internos del bot, como reestablecer la base de datos.
        """
        if admins is None:
            admins = []
        self.msg = None

        self.db = ShelveDB("stickerDB")
        self.token = token
        self.admins = admins

        self.bot = telepot.Bot(self.token)
        self.answerer = InlineHandler(self.bot)
        self.id = self.bot.getMe()['id']

    def run(self):
        """Corre el bot."""
        MessageLoop(self.bot, {'chat': self.chat_handle, 'inline_query': self.inline_handle,
                               'chosen_inline_result': on_chosen_inline_result}).run_as_thread()
        print('Listening ...')

        while True:
            time.sleep(10)

    # Comandos normales
    def chat_handle(self, msg):
        """
        Handle de los mensajes recibidos por chat.

        :param msg: Mensaje.
        """
        self.msg = msg
        content_type, chat_type, chat_id = telepot.glance(msg)
        print(content_type, chat_type, chat_id)
        # Si comienza un chat.
        if content_type == 'new_chat_member':
            if msg['new_chat_member']['id'] == self.id:
                self.greet(chat_id)
        if not content_type == 'text':  # Ignora los mensajes que no sean texto
            return
        text = msg['text']
        self.exec_command(text, chat_id, chat_type)

    def exec_command(self, command, chat_id, chat_type):
        """
        Ejecuta un comando.

        :param command:     Comando a ejecutar.
        :param chat_id:     ID del chat desde el que se llama al comando.
        :param chat_type:   Tipo del chat desde el que se llama al comando.
        """
        command = command.split(" ")
        if len(command) >= 1:
            if command[0] == '/start' and chat_type == 'private':
                self.greet(chat_id)
                self.bot.sendMessage(chat_id, "Can I /help you?")
            elif command[0] == '/backup' and chat_id in self.admins:
                self.backup_db()
            elif (command[0] == '/help' and chat_type == 'private') or command[0] == '/help@stickfixbot':
                self.help(chat_id)
            elif command[0] == '/tags' or command[0] == '/tags@stickfixbot':
                self.show_tags(chat_id)
            elif command[0] == '/resetDB':
                self.reset_db(self.msg['from']['id'])
        if len(command) >= 2:
            if command[0] == '/add' or command[0] == '/add@stickfixbot':
                if command[1] == 'p':
                    self.add(command[2], True)
                else:
                    self.add(command[1])
            elif command[0] == '/deleteFrom':
                if command[1] == 'p':
                    self.delete_from_tag(command[2], chat_id, True)
                else:
                    self.delete_from_tag(command[1], chat_id)
            elif command[0] == '/deleteTag':
                self.delete_tag(command[1], chat_id, self.msg['from']['id'])
            elif command[0] == '/get' and chat_type == 'private':
                if command[1] == 'p':
                    self.get_all(command[2], chat_id, True)
                else:
                    self.get_all(command[1], chat_id)

    def add(self, tag, is_personal=False):
        """
        Asocia un sticker con un tag.
        Si el tag no existe, se crea; si el sticker ya está relacionado con el tag, se ignora.

        :param is_personal: Define si el sticker se agrega a una colección privada o comunitaria.
        :param tag:         Etiqueta del sticker.
        """
        try:
            user_id = ''
            if is_personal:
                user_id = str(self.msg['from']['id']) + ":"
            reply = self.msg['reply_to_message']
            reply_type = telepot.glance(reply)[0]
            if reply_type == 'sticker' and is_valid(tag):
                sticker = reply['sticker']['file_id']
                result = self.db.add_item(user_id + tag, sticker)
                if result:
                    print("Added sticker to " + tag)
                else:
                    print("Sticker was already stored")
        except KeyError as e:
            print(e)

    def delete_from_tag(self, tag, chat_id, is_personal=False):
        try:
            user_id = ''
            if is_personal:
                user_id = str(self.msg['from']['id']) + ":"
            sticker_id = self.msg['reply_to_message']['sticker']['file_id']
            self.db.delete_from_key(user_id + tag, sticker_id)
            self.bot.sendMessage(chat_id, "Sticker successfully deleted from " + tag)
        except KeyError as e:
            self.bot.sendMessage(chat_id, "Couldn't find the sticker.")
            print(e)

    def delete_tag(self, tag, chat_id, user_id):
        """
        Elimina un tag de la base de datos.
        
        :param tag:     Tag a eliminar
        :param chat_id: Chat desde el que se llamó el comando.
        :param user_id: ID del usuario que invocó el comando
        """
        if user_id in self.admins:
            if self.db.delete_by_key(tag):
                self.bot.sendMessage(chat_id, "Tag " + tag + " was deleted successfully.")
            else:
                self.bot.sendMessage(chat_id, "The tag you're trying to delete doesn't exist.")
        else:
            self.bot.sendMessage(chat_id, "You have no power over me. Please contact an admin.")

    def get_all(self, tag, chat_id, is_personal=False):
        """
        Envía todos los stickers para un tag específico.

        :param is_personal:
        :param tag:     Etiqueta de los stickers.
        :param chat_id: ID del chat.
        """
        try:
            if is_personal:
                items = self.db.get_item(str(chat_id) + ":" + tag)
            else:
                items = list(set.union(set(self.db.get_item(str(chat_id) + ":" + tag)), set(self.db.get_item(tag))))
                items.sort()
            for item in items:
                self.bot.sendSticker(chat_id, item)
        except TypeError as e:
            self.bot.sendMessage(chat_id, "Nothing to get. Tag may not have been initialized.")
            print(e)

    def show_tags(self, chat_id):
        """
        Envía un mensaje conteniendo todos los tags almacenados.
        
        :param chat_id:
        """
        tags = []
        for tag in self.db.get_keys():
            if is_valid(tag):
                tags.append(tag + " (" + str(len(self.db.get_item(tag))) + ")\n")
        if len(tags) == 0:
            self.bot.sendMessage(chat_id, "No tags here.")
            return
        tags.sort()
        message = ""
        for tag in tags:
            message += tag
        self.bot.sendMessage(chat_id, message)

    def reset_db(self, user_id):
        """
        Reestablece la base de datos completa.
        Para llamar a este comando, se deben tener privilegios de administrador.
                
        :param user_id: ID del usuario que invoca el comando.
        """
        if user_id in self.admins:
            self.bot.sendMessage(user_id, "Wait a moment...")
            self.backup_db()
            self.db.reset()
            self.bot.sendMessage(user_id, "Database emptied.")
        else:
            self.bot.sendMessage(user_id, "You have no power over me. Please contact an admin.")

    def backup_db(self):
        db = open("stickerDB.bak")
        from datetime import datetime
        date = datetime.now().strftime("%c")
        for admin in self.admins:
            self.bot.sendDocument(admin, db, date)

    # Inline

    def inline_handle(self, msg):
        def compute():
            query_id, from_id, query_string = telepot.glance(msg, flavor='inline_query')
            print('%s: Computing for: %s' % (threading.current_thread().name, query_string))
            command = query_string.split(" ")
            try:
                # Pick random
                if command[0] == 'r':
                    if len(command) >= 2:
                        item = random.choice(self.db.get_item(command[1]))
                        stickers.append(InlineQueryResultCachedSticker(type="sticker", id=item, sticker_file_id=item))
                else:
                    if command[0] == 'p':
                        if len(command) >= 2:
                            items = self.db.get_item(str(from_id) + ':' + command[1])
                    else:
                        try:
                            items = list(set.union(set(self.db.get_item(str(from_id) + ":" + command[0])),
                                                   set(self.db.get_item(command[0]))))
                            items.sort()
                        except TypeError:
                            items = self.db.get_item(command[0])

                    if len(items) >= 50:  # Si el inline tiene más de 50 elementos, muestra 50 aleatorios.
                        items = random.sample(items, 50)
                        items.sort()
                    for item in items:
                        stickers.append(
                            InlineQueryResultCachedSticker(type="sticker", id=item, sticker_file_id=item))
            except TypeError as e:
                print(e)

            return stickers

        stickers = []
        self.answerer.answer(msg, compute)  # Extra

    def greet(self, chat_id):
        """
        Saluda.

        :param chat_id: ID del chat.
        """
        self.bot.sendSticker(chat_id, 'CAADBAADTAADqAABTgXzVqN6dJUIXwI')  # file_id del fogs helo

    def help(self, chat_id):
        self.bot.sendMessage(chat_id,
                             "Yo! I'm StickFix, I can link keywords with stickers so you can manage them "
                             'more easily.\n'
                             'You can control me by sending me these commands:\n'
                             '/tags - _Sends a message with all the tags that have stickers_\n'
                             '/add <tag> - _Links a sticker with a tag, where <tag> is a hashtag. For this '
                             'to work you have to reply to a message that contains a sticker with the '
                             'command; I need access to the messages to do this._\n'
                             '/pickRandom <tag> - _Sends a random sticker tagged with <tag>._\n'
                             '/deleteFrom <tag> - _Works like /add, it unlinks a sticker from a tag._\n'
                             '\n'
                             '*In private:*\n'
                             '/get <tag> - _Sends all stickers tagged with <tag>._\n'
                             '\n'
                             'You can also call me inline like `@stickfixbot #tag` to see a list of all the '
                             'stickers you have tagged with #tag.',
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
                        self._bot.answerInlineQuery(query_id, ans, cache_time=0, is_personal=True)
                    elif isinstance(ans, tuple):
                        self._bot.answerInlineQuery(query_id, *ans, cache_time=0, is_personal=True)
                    elif isinstance(ans, dict):
                        self._bot.answerInlineQuery(query_id, **ans, cache_time=0, is_personal=True)
                    else:
                        raise ValueError('Invalid answer format')
                finally:
                    with self._lock:
                        # Delete only if I have NOT been cancelled.
                        if not self._cancelled:
                            del self._workers[from_id]

                            # If I have been cancelled, that position in `outerself._workers`
                            # no longer belongs to me. I should not delete that key.

        # Several threads may access `outerself._workers`. Use `outerself._lock` to protect.
        with self._lock:
            if from_id in self._workers:
                self._workers[from_id].cancel()

            self._workers[from_id] = Worker(self._bot, self._lock, self._workers)
            self._workers[from_id].start()
