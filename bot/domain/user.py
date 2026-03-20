"""User domain model and sticker-tag behavior."""

import random
from enum import Enum
from typing import Dict, List, Set

from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)


class UserModes(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class Switch(str, Enum):
    ON = "on"
    OFF = "off"


SF_PUBLIC = "SF-PUBLIC"


class StickfixUser:
    OFF = False
    ON = True
    _shuffle: bool
    cached_stickers: Dict[str, List[str]]
    stickers: Dict[str, List[str]]

    def __init__(self, user_id):
        """
        Creates a StickfixBot user with default values.

        :param user_id:
            ID of the user.
        """
        self.id = user_id
        self.stickers = dict()
        self.cached_stickers = {}
        self.private_mode = False
        self._shuffle = False

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @shuffle.setter
    def shuffle(self, value):
        self._shuffle = value

    @property
    def cache(self) -> Dict[str, List[str]]:
        return self.cached_stickers

    def get_effective_pack(self, public_user=None):
        if self.private_mode or public_user is None:
            return self
        return public_user

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
                self.stickers = {tag: [sticker_id]}
            else:
                if tag in self.stickers:
                    aux = self.stickers[tag]
                    if sticker_id not in aux:
                        aux.append(sticker_id)
                else:
                    aux = [sticker_id]
                self.stickers[tag] = sorted(aux)
        logger.info(f"Sticker added to {self.id} pack with tags: {', '.join(sticker_tags)}")

    def link_sticker(self, sticker_id, sticker_tags, public_user=None):
        self.get_effective_pack(public_user).add_sticker(sticker_id, sticker_tags)

    def get_stickers(self, sticker_tag: str) -> Set[str]:
        """
        Gets all stickers from the database that matches the tag.

        :param sticker_tag:
            Tag linked with the stickers.
        :returns:
            Set with all the stickers that matches the tag.
        """
        if self.cache:
            try:
                return set(self.cache[sticker_tag])
            except KeyError:
                pass
        if sticker_tag in self.stickers:
            return set(self.stickers[sticker_tag])
        return set()

    def resolve_sticker_list(self, tags: List[str], public_user=None) -> List[str]:
        if not tags:
            return []
        stickers = []
        public_pack = None if self.private_mode else public_user
        for tag in tags:
            match = set()
            if public_pack is not None:
                match = public_pack.get_stickers(tag)
            match = match.union(self.get_stickers(tag))
            stickers.append(match)
            self.cache[tag] = list(match)
        return list(set.intersection(*stickers)) if stickers else []

    def get_shuffled_sticker_list(self, tags: List[str], public_user=None) -> List[str]:
        stickers = self.resolve_sticker_list(tags, public_user=public_user)
        if self.shuffle:
            random.shuffle(stickers)
        return stickers

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
        self.cached_stickers = {}

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

    def unlink_sticker_from_pack(self, sticker_id, sticker_tags, public_user=None):
        self.get_effective_pack(public_user).unlink_sticker(sticker_id, sticker_tags)
