#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helper class to manage a shelve database more easily.
"""
import os

import yaml


class StickfixDB:
    def __init__(self, name: str):
        self.__name__ = name
        self.__data_dir = "../../data"
        yaml_path = f"{self.__data_dir}/{name}.yaml"
        if not os.path.exists(self.__data_dir):
            os.makedirs(self.__data_dir)
            with open(yaml_path, "w") as fp:
                yaml.dump({ }, fp, yaml.Dumper)
        with open(yaml_path, "r") as fp:
            self.__db = yaml.load(fp, yaml.FullLoader)

    def __contains__(self, item):
        return item in self.__db

    def __setattr__(self, key, value):
        self.__db[key] = value

    def __delattr__(self, item):
        del self.__db[item]

    def __getattr__(self, item):
        return self.__db[item]

    def __len__(self):
        return len(self.__db)

    def get_keys(self):
        return self.__db.keys()
