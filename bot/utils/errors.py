#!/usr/bin/python
# coding=utf-8

"""
This module defines the exceptions used by `StickfixBot`.
"""

__author__ = "Ignacio Slater Muñoz <ignacio.slater@ug.uchile.cl>"
__version__ = "1.5"


class StickfixError(Exception):
    """
    Base class for exceptions in this module
    
    Attributes:
        err_message -- message sent by the error.
        err_cause -- reason that caused the exception.
    """
    
    def __init__(self, err_message='', err_cause=None):
        self.message = err_message
        self.cause = err_cause if err_cause is not None else 'UNKNOWN.'


class InputError(StickfixError):
    """
    Exception raised when the arguments passed as input to the bot are incorrect.
    """


class NoStickerError(StickfixError):
    """
    Exception raised when the bot can't find a sticker in a message.
    """


class WrongContextError(StickfixError):
    """
    Exception raised when the bot tries to execute a command from the wrong context.
    For example, this exception should be raised if a command can only be called from a private chat and is being
    called from a group chat.
    """


class InsufficientPermissionsError(StickfixError):
    """
    Exception raised when a user tries to call a command without the appropriate permissions.
    """
