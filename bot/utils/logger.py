""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
import logging
from logging.handlers import RotatingFileHandler


class ILogger:
    """ Base class for handling bot logs.   """

    def debug(self, msg: str) -> None:
        """ Logs a message with debug level.    """
        raise NotImplementedError

    def info(self, msg: str) -> None:
        """ Logs a message with info level.    """
        raise NotImplementedError

    def error(self, msg: str) -> None:
        """ Logs a message with error level.    """
        raise NotImplementedError

    def critical(self, msg: str) -> None:
        """ Logs a message with error level.    """
        raise NotImplementedError


class StickfixLogger(ILogger):
    """ Wrapper class to handle the bot logs. """
    __logger: logging.Logger

    def __init__(self, context: str):
        self.__logger = logging.getLogger(context)
        self.__logger.setLevel(logging.DEBUG)
        console_logger = logging.StreamHandler()
        console_logger.setLevel(logging.DEBUG)
        console_logger.setFormatter(
            logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
        self.__logger.addHandler(console_logger)
        file_logger = RotatingFileHandler(filename='logs/stickfix.log', encoding="utf-8",
                                          maxBytes=50000, backupCount=2)
        file_logger.setLevel(logging.INFO)
        file_logger.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.__logger.addHandler(file_logger)

    def debug(self, msg: str) -> None:
        self.__logger.debug(msg)

    def info(self, msg: str) -> None:
        self.__logger.info(msg)

    def error(self, msg: str) -> None:
        self.__logger.error(msg)

    def critical(self, msg: str) -> None:
        self.__logger.critical(msg)


class NullLogger(ILogger):
    """ Null logger that doesn't print or save anything.    """

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass

    def critical(self, msg: str) -> None:
        pass
