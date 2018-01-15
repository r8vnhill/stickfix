#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
"""

__author__ = "Ignacio Slater Muñoz <ignacio.slater@ug.uchile.cl>"
__version__ = "1.1.2"


class StickfixUser:
    OFF, ON = range(2)
    
    def __init__(self, user_id):
        self.id = user_id
        self.stickers = dict()
        self.private_mode = self.OFF
    
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
