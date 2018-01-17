#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helper class to manage a shelve database more easily.
"""

import shelve

__author__ = "Ignacio Slater Muñoz <ignacio.slater@ug.uchile.cl>"
__version__ = "2.0"


class ShelveDB:
    def __init__(self, name):
        self.__name__ = name
    
    def __contains__(self, item):
        with shelve.open(self.__name__) as db:
            return item in db
    
    def add_item(self, key, data):
        """Adds an item to the database. Overrides it if the key already exists."""
        with shelve.open(self.__name__) as db:
            db[key] = data
    
    def delete_by_key(self, key):
        with shelve.open(self.__name__) as db:
            try:
                del db[key]
                return True
            except KeyError as _:
                return False
    
    def get_item(self, key):
        with shelve.open(self.__name__) as db:
            try:
                return db[key]
            except KeyError:
                return []

    def is_empty(self):
        """Checks if the database is empty."""
        return len(self.get_keys()) == 0
    
    def get_keys(self):
        with shelve.open(self.__name__) as db:
            return list(db.keys())
