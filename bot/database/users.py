""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import random
from enum import Enum

from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)


class UserModes(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class Switch(str, Enum):
    ON = "on"
    OFF = "off"


class StickfixUser:
    OFF = False
    ON = True
    _shuffle: bool

    def __init__(self, user_id):
        """
        Creates a StickfixBot user with default values.
        
        :param user_id:
            ID of the user.
        """
        self.id = user_id
        self.stickers = dict()
        self.cached_stickers = { }
        self.private_mode = False
        self._shuffle = False

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    def add_sticker(self, sticker_id, sticker_tags):
        """
        Adds a sticker to the database with the specified tags.

        :param sticker_id:
            ID of the sticker to be added to the user.
        :param sticker_tags:
            List of the tags that will represent the sticker.
        """
        for tag in sticker_tags:
            if self.stickers is None:
                self.stickers = { tag: [sticker_id] }
            else:
                if tag in self.stickers:
                    aux = self.stickers[tag]
                    if sticker_id not in aux:
                        aux.append(sticker_id)
                else:
                    aux = [sticker_id]
                self.stickers[tag] = sorted(aux)
        logger.info(f"Sticker added to {self.id} pack with tags: {', '.join(sticker_tags)}")

    def get_stickers(self, sticker_tag):
        """
        Gets all stickers from the database that matches the tag.

        :param sticker_tag:
            Tag linked with the stickers.
        :returns:
            Set with all the stickers that matches the tag.
        """
        if sticker_tag in self.stickers:
            return set(self.stickers[sticker_tag])
        return set()

    def random_tag(self):
        """Returns a random tag from the database."""
        tag_list = list(self.stickers.keys())
        if len(tag_list) == 0:
            return []
        return [random.choice(tag_list)]

    def remove_cached_stickers(self, user_id=None):
        """
        Removes the cached stickers for the user.
        
        :param user_id:
            Usually the same id as `self.id`, but `SF-PUBLIC` can cache stickers for other users.
        """
        if user_id in self.cached_stickers:
            del self.cached_stickers[user_id]

    def unlink_sticker(self, sticker_id, sticker_tags):
        """
        Removes a sticker with the specified tags from the database.
        
        :param sticker_id:
            ID of the sticker to be removed.
        :param sticker_tags:
            List of tags that contains the sticker.
        """
        for tag in sticker_tags:
            if tag in self.stickers:
                self.stickers[tag] = [x for x in self.stickers[tag] if x != sticker_id]
                if len(self.stickers[tag]) == 0:
                    del self.stickers[tag]
        if sticker_tags:
            logger.info(f"Removed sticker {sticker_id} from tags {', '.join(sticker_tags)}")

    @shuffle.setter
    def shuffle(self, value):
        self._shuffle = value
