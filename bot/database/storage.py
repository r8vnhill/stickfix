#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helper class to manage a shelve database more easily.
"""
import os
import shutil
from typing import Dict, KeysView

import yaml

from bot.database.users import StickfixUser
from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)


class StickfixDB(dict):
    __db: Dict

    def __init__(self, name: str) -> None:
        super(StickfixDB, self).__init__()
        self.__name__ = name
        self.__data_dir = "data"
        self.__yaml_path = f"{self.__data_dir}/{name}.yaml"
        if not os.path.exists(self.__data_dir):
            os.makedirs(self.__data_dir)
            with open(self.__yaml_path, "w") as fp:
                yaml.dump({ }, fp, yaml.Dumper)
        self.load_db()

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
            logger.debug("Database saved.")
        try:
            self.load_db()
        except yaml.YAMLError:
            logger.error(f"Unexpected error loading {self.__yaml_path}")
            try:
                logger.debug(f"Loading {bak_1}")
                self.load_db()
                shutil.copy(bak_1, self.__yaml_path)
            except yaml.YAMLError:
                logger.error(f"Unexpected error loading {bak_1}")
                logger.debug(f"Loading {bak_2}")
                self.load_db()
                shutil.copy(bak_2, self.__yaml_path)

    def load_db(self) -> None:
        """ Reads the database from a file. """
        path = self.__yaml_path
        with open(path, "r") as fp:
            self.__db = yaml.load(fp, yaml.Loader)
            logger.debug(f"Loaded database from {path}")
