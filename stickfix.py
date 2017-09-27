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


def _on_chosen_inline_result(msg):
    """
    Represents a result of an inline query that was chosen by the user and sent
    to their chat partner.
    """
    result_id, from_id, query_string = telepot.glance(
        msg, flavor='chosen_inline_result')
    print('Chosen Inline Result:', result_id, from_id, query_string)


def _is_valid(tag):
    """
    Checks if a hashtag is valid.

    :param tag: Tag to check.
    :return:
    """
    return re.fullmatch("#[A-Za-z][\w_]*", tag) is not None


# noinspection PyUnusedLocal
class StickerHelperBot:
    """
    Base class for @stickfixbot.
    This class implements functions to help manage and store stickers in
    telegram using chat commands and inline queries.
    """

    def __init__(self, token, admins=None):
        """
        Initializes the bot.

        :param token:
            Bot's TOKEN.
        :param admins:
            ID of the users that have administrator privileges, this is needed
            to manage the database using chat commands.
        """
        self._msg = None

        self._db = ShelveDB("stickerDB")
        self._admins = [] if (admins is None) else admins

        self._bot = telepot.Bot(token)
        self._answerer = InlineHandler(self._bot)
        self._id = self._bot.getMe()['id']

        self._chat_cmd = {
            "/start": self.greet,
            "/backup": self._backup_db,
            "/help": self.help,
            "/tags": self._show_tags,
            "/resetDB": self._reset_db,
            "/add": self._add,
            "/deleteFrom": self._delete_from_tag,
            "/deleteTags": self._delete_tag,
            "/get": self._get_all,
            "/restore": self._restore
        }

    def run(self):
        """
        Starts the bot.
        """
        handle = {
            'chat': self._chat_handle,
            'inline_query': self.inline_handle,
            'chosen_inline_result': _on_chosen_inline_result
        }
        MessageLoop(self._bot, handle).run_as_thread()
        print('Listening ...')

        while True:
            time.sleep(10)

    def _chat_handle(self, msg):
        """
        Handles the messages received in chat.

        :param msg:
            Message received.
        """
        self._msg = msg
        content_type, chat_type, chat_id = telepot.glance(msg)
        print(content_type, chat_type, chat_id)

        if content_type == 'new_chat_member':  # If the bot joins a chat.
            if msg['new_chat_member']['id'] == self._id:
                self.greet(chat_id)

        if not content_type == 'text':  # Ignores all non-text messages
            return

        txt = msg['text']
        self._exec_command(txt, chat_id, chat_type)

    def _exec_command(self, msg, chat_id, chat_type):
        """
        Executes a command.

        :param msg:
            Message.
        :param chat_id:
            ID of the chat that sent the message.
        :param chat_type:
            Chat type from which the message was sent.
        """
        msg = msg.split(" ")
        cmd = msg[0]
        params = msg[1:] if len(msg) > 1 else None

        if cmd in self._chat_cmd:
            self._chat_cmd[cmd](chat_id, chat_type, params)

    def _add(self, chat_id, chat_type, params):
        """
        Links a sticker with a tag.
        If the tag doesn't exist, it's created; if the sticker is already linked
        with the tag, it's ignored.

        :param chat_id:
            Unused.
        :param chat_type:
            Unused.
        :param params:
            Parameters that are passed to the command.
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
                        if not _is_valid(tag):
                            continue
                        result = self._db.add_item(user_id + tag, sticker)
                        if result:
                            print("Added sticker to " + tag)
                        else:
                            print("Sticker was already stored")
        except KeyError as e:
            print(e)

    def _delete_from_tag(self, chat_id, chat_type, params):
        """
        Deletes a sticker from a tag.

        :param chat_id:
            ID of the chat from which the command was called.
        :param chat_type:
            Unused.
        :param params:
            Parameters that are passed to the command.
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

    def _delete_tag(self, chat_id, chat_type, params):
        """
        Deletes a tag from the database.

        :param chat_id:
            ID of the chat from which the command was called.
        :param chat_type:
            Unused.
        :param params:
            Parameters that are passed to the command.
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

    def _get_all(self, chat_id, chat_type, params):
        """
        Send the stickers that match with the selected tags.

        :param chat_id:
            ID of the chat from which the command was called.
        :param chat_type:
            Chat type from which the message was sent.
        :param params:
            Parameters that are passed to the command.
        """
        if chat_type == 'private' and params is not None:
            i = 1 if params[0] == 'p' else 0
            stickers = self.get_stickers(chat_id, params[i:], bool(i))
            if len(stickers) == 0:
                self._bot.sendMessage(chat_id, "Nothing to get.")
                return

            for item in stickers:
                self._bot.sendSticker(chat_id, item)

    def _show_tags(self, chat_id, chat_type, params):
        """
        Sends a message containing all the stored tags.

        :param chat_id:
            ID of the chat from which the command was called.
        :param params:
            Parameters that are passed to the command.
        :param chat_type:
            Unused.
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
                if _is_valid(tag):
                    tags.append(
                        tag + " (" + str(len(self._db.get_item(tag))) + ")")

        if len(tags) == 0:
            self._bot.sendMessage(chat_id, "No tags here.")
            return

        tags.sort()
        message = '\n'.join(tags)
        self._bot.sendMessage(chat_id, message)

    def _reset_db(self, chat_id, chat_type=None, params=None):
        """
        Resets the database.

        :param params:
            Unused.
        :param chat_type:
            Unused.
        :param chat_id:
            ID of the chat from which the command was called.
        """
        if chat_id in self._admins:
            self._bot.sendMessage(chat_id, "Wait a moment...")
            self._backup_db(chat_id)
            self._db.reset()
            self._bot.sendMessage(chat_id, "Database emptied.")
        else:
            self._bot.sendMessage(
                chat_id,
                "You have no power over me. Please contact an admin.")

    def _backup_db(self, chat_id, chat_type=None, params=None):
        """
        Sends a message with a backup of the database.

        :param chat_id:
            ID of the chat from which the command was called.
        :param chat_type:
            Unused.
        :param params:
            Unused.
        """
        if chat_id in self._admins:
            import os
            with open("stickerDB.json", 'w') as fp:
                fp.write(self._db.get_db())
            files = [f for f in os.listdir('.') if os.path.isfile(f) and f.startswith("stickerDB")]
            for file in files:
                with open(file) as db:
                    from datetime import datetime
                    date = datetime.now().strftime("%c")
                    for admin in self._admins:
                        self._bot.sendDocument(admin, db, date)

    def _restore(self, chat_id, chat_type=None, params=None):
        """
        Restores the database to the last backup.
        
        :param chat_id:
        :param chat_type:
        :param params:
        :return:
        """
        if chat_id in self._admins:
            self._bot.sendMessage(chat_id, "Wait a moment...")
            self._db.update("stickerDB.json")
            self._bot.sendMessage(chat_id, "Database was restored to the last backup.")

    def inline_handle(self, msg):
        """
        Handles the messages received via inline.

        :param msg:
            Message received.
        """
        self._msg = msg
        self._answerer.answer(msg, self.compute)

    def compute(self):
        """
        Computes the inline query and returns the result.

        :return:
            List of stickers to be shown to the user.
        """
        stickers = []
        query_id, from_id, query_string = telepot.glance(self._msg,
                                                         flavor='inline_query')
        print('%s: Computing for: %s' % (
            threading.current_thread().name, query_string))
        cmd = query_string.split(" ")
        i = 0
        is_personal, is_random = False, False
        if len(cmd) > 1:
            if (cmd[0] == 'p' or cmd[1] == 'p') and not _is_valid(cmd[0]):
                is_personal = True
                i += 1
            if (cmd[0] == 'r' or cmd[1] == 'r') and not _is_valid(cmd[0]):
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
        """
        Get all the stickers that match with the specified tags.

        :param user_id:
            ID of the user that's calling the command.
        :param tags:
            List of tags that that are going to be searched for.
        :param is_personal:
            Indicates if the stickers are part of a personal collection.
        :param is_random:
            Indicates if the method should pick a random sticker from the tags.
        :return:
            List of the stickers that match the selected tags.
        """
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
        Greets the user.

        :param chat_id:
            ID of the chat from which the command was called.
        :param chat_type:
            Unused.
        :param params:
            Unused.
        """
        self._bot.sendSticker(chat_id, 'CAADBAADTAADqAABTgXzVqN6dJUIXwI')
        self._bot.sendMessage(chat_id, "Can I /help you?")

    def help(self, chat_id, chat_type=None, params=None):
        """
        Sends a message with help to the user.

        :param chat_id:
            ID of the chat from which the command was called.
        :param chat_type:
            Unused.
        :param params:
            Unused.
        """
        self._bot.sendMessage(
            chat_id,
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
            parse_mode="Markdown"
        )


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
