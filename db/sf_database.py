#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module contains the implementation of the database that manages Stickfix's data.
"""
import json
import shelve
from json import JSONDecodeError
from sqlite3.dbapi2 import Connection, Cursor
from typing import Dict, Union

__author__ = "Ignacio Slater Muñoz <ignacio.slater@ug.uchile.cl>"
__version__ = "3.0.0002"

class StickfixDB:
    """
    Class that represents the database of the bot
    """
    _name: str
    _conn: Connection
    _db_cursor: Cursor

    def __init__(self, name: str):
        self._name = name

    def __contains__(self, item):
        try:
            with open(f"{self._name}.json", 'r') as json_db:
                return item in json.load(json_db)
        except (FileNotFoundError, JSONDecodeError):
            return False

    def __getitem__(self, key: str) -> Union[bool, Dict]:
        """
        Retrieves an item from the database
        :param key: the key of the element looked for
        :return: the element that matches the key; otherwise, it returns False
        """
        try:
            with open(f"{self._name}.json", 'r') as json_db:
                return json.load(json_db)[key]
        except (FileNotFoundError, JSONDecodeError):
            return False

    def __setitem__(self, key: str, value: Dict):
        """
        Sets the value of an element in the database.

        :param key: id of the element
        :param value: content of the element
        """
        with open(f"{self._name}.json", 'w+') as json_db:
            try:
                db = json.load(json_db)
            except JSONDecodeError:
                db = {}
            db[key] = value
            json.dump(db, json_db)

    def _get_item(self, keys: Dict):
        for key, value in keys.values():
            self._db_cursor.execute('SELECT * FROM ? WHERE ? = ?',
                                    (self._name, key, value))
            print(self._db_cursor.fetchone())

    def add_item(self, key, data):
        """Adds an item to the database. Overrides it if the key already exists."""
        with shelve.open(self._name) as db:
            db[key] = data

    def delete_by_key(self, key):
        with shelve.open(self._name) as db:
            try:
                del db[key]
                return True
            except KeyError as _:
                return False

    def get_item(self, key):
        with shelve.open(self._name) as db:
            try:
                return db[key]
            except KeyError:
                return False

    def is_empty(self):
        """Checks if the database is empty."""
        return len(self.get_keys()) == 0

    def get_keys(self):
        with shelve.open(self._name) as db:
            return list(db.keys())
