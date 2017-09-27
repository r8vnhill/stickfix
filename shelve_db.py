#!/usr/bin/env python
import json
import shelve

__author__ = "Ignacio Slater Muñoz"
__email__ = "ignacio.slater@ug.uchile.cl"


class ShelveDB:
    def __init__(self, name):
        self._name = name

    def add_item(self, key, data):
        with shelve.open(self._name) as db:
            if key in db:
                if data in db[key]:
                    return False
                tmp = db[key]
                tmp.append(data)
                tmp.sort()
                db[key] = tmp
            else:
                db[key] = [data]
        return True

    def delete_by_key(self, key):
        """
        Elimina una llave de la base de datos.
        
        :param key: Llave.
        :return: True si se eliminó la llave, False si no.
        """
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
            except KeyError as e:
                # print(e)
                return []

    def reset(self):
        with shelve.open(self._name) as db:
            for key in list(db.keys()):
                del db[key]

    def delete_if_startswith(self, match):
        """
        Elimina todas las entradas que comiencen por string.

        :param match: Substring de los elementos que se quieren eliminar.
        """
        with shelve.open(self._name) as db:
            for key in list(db.keys()):
                if key.startswith(match):
                    del db[key]

    def get_keys(self):
        """
        Imprime todas las llaves de la base de datos.
        """
        with shelve.open(self._name) as db:
            return list(db.keys())

    def delete_from_key(self, key, element):
        """

        :param key:
        :param element:
        :return:
        """
        with shelve.open(self._name) as db:
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
        with shelve.open(self._name) as db:
            for key in db.keys():
                d += '  "' + key + '"' + ": " + json.dumps(db[key])
                if i < len(db.keys()) - 1:
                    d += ","
                d += "\n"
                i += 1
        d += "}"
        return d

    def update(self, file):
        """
        Updates the shelve with a dictionary.
        
        :param file:
            Dictionary stored in a JSON file.
        """
        with shelve.open(self._name) as db:
            with open(file, 'r') as fp:
                data = json.load(fp)
            for key in data.keys():
                db[key] = data[key]
