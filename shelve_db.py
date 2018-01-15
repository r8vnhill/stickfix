#!/usr/bin/env python
import json
import shelve

__author__ = "Ignacio Slater Muñoz"
__email__ = "ignacio.slater@ug.uchile.cl"
__version__ = "1.1"


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
            except KeyError as e:
                # print(e)
                return []

    def reset(self):
        with shelve.open(self.__name__) as db:
            for key in list(db.keys()):
                del db[key]

    def delete_if_startswith(self, match):
        with shelve.open(self.__name__) as db:
            for key in list(db.keys()):
                if key.startswith(match):
                    del db[key]

    def get_keys(self):
        with shelve.open(self.__name__) as db:
            return list(db.keys())

    def delete_from_key(self, key, element):
        with shelve.open(self.__name__) as db:
            if element in db[key]:
                db[key] = [x for x in db[key] if x != element]
                if len(db[key]) == 0:
                    del db[key]
            else:
                raise KeyError

    def get_db(self):
        """
        Gets the db as a string.
        
        :return: A string representation of the database following the format of a JSON file.
        """
        d = "{\n"
        i = 0
        with shelve.open(self.__name__) as db:
            for key in db.keys():
                d += '  "' + key + '"' + ": " + json.dumps(db[key])
                if i < len(db.keys()) - 1:
                    d += ","
                d += "\n"
                i += 1
        d += "}"
        return d

    def update_from_file(self, file):
        """
        Updates the shelve with a dictionary.
        
        :param file:
            Dictionary stored in a JSON file.
        """
        with shelve.open(self.__name__) as db:
            with open(file, 'r') as fp:
                data = json.load(fp)
            for key in data.keys():
                db[key] = data[key]

    def update_from_string(self, text):
        """
        Updates the shelve with a dictionary.
        
        :param text:
            Dictionary stored in a JSON string.
        """
        with shelve.open(self.__name__) as db:
            data = json.loads(text)
            for key in data.keys():
                db[key] = data[key]
