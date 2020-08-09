#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helper class to manage a shelve database more easily.
"""
import os
from typing import KeysView

import yaml

from bot.database.users import StickfixUser


class StickfixDB(dict):
    def __init__(self, name: str) -> None:
        super(StickfixDB, self).__init__()
        self.__name__ = name
        self.__data_dir = "data"
        yaml_path = f"{self.__data_dir}/{name}.yaml"
        if not os.path.exists(self.__data_dir):
            os.makedirs(self.__data_dir)
            with open(yaml_path, "w") as fp:
                yaml.dump({ }, fp, yaml.Dumper)
        with open(yaml_path, "r") as fp:
            self.__db = yaml.load(fp, yaml.Loader)

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
