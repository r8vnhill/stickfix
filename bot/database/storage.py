#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helper class to manage a shelve database more easily.
"""
import os
import shutil
from typing import KeysView

import yaml

from bot.database.users import StickfixUser
from bot.utils.logger import ILogger, NullLogger, StickfixLogger


class StickfixDB(dict):
    __logger: ILogger

    def __init__(self, name: str, test: bool = False) -> None:
        super(StickfixDB, self).__init__()
        self.__logger = NullLogger() if test else StickfixLogger(__name__)
        self.__name__ = name
        self.__data_dir = "data"
        self.__yaml_path = f"{self.__data_dir}/{name}.yaml"
        if not os.path.exists(self.__data_dir):
            os.makedirs(self.__data_dir)
            with open(self.__yaml_path, "w") as fp:
                yaml.dump({ }, fp, yaml.Dumper)
        self.__load_db(self.__yaml_path)

    def __contains__(self, item) -> bool:
        return item in self.__db

    def __setitem__(self, key, value) -> None:
        self.__db[key] = value

    def __delitem__(self, key) -> None:
        del self.__db[key]

    def __getitem__(self, item) -> StickfixUser:
        return self.__db[item]

    def __len__(self) -> int:
        return len(self.__db)

    def get_keys(self) -> KeysView[str]:
        return self.__db.keys()

    def save(self) -> None:
        """ Saves the database. """
        bak_2 = f"{self.__yaml_path}_2.bak"
        shutil.copy(self.__yaml_path, bak_2)
        bak_1 = f"{self.__yaml_path}_1.bak"
        shutil.copy(self.__yaml_path, bak_1)
        with open(self.__yaml_path, "w") as fp:
            yaml.dump(self.__db, fp, yaml.Dumper)
            self.__logger.debug("Database saved.")
        try:
            self.__load_db(self.__yaml_path)
        except yaml.YAMLError:
            self.__logger.error(f"Unexpected error loading {self.__yaml_path}")
            try:
                self.__logger.debug(f"Loading {bak_1}")
                self.__load_db(bak_1)
                shutil.copy(bak_1, self.__yaml_path)
            except yaml.YAMLError:
                self.__logger.error(f"Unexpected error loading {bak_1}")
                self.__logger.debug(f"Loading {bak_2}")
                self.__load_db(bak_2)
                shutil.copy(bak_2, self.__yaml_path)

    def __load_db(self, path: str) -> None:
        """ Reads the database from a file. """
        with open(path, "r") as fp:
            self.__db = yaml.load(fp, yaml.Loader)
