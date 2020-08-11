""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""


class StickfixException(Exception):
    """
    Base class for exceptions in this module
    
    Attributes:
        err_message -- message sent by the error.
        err_cause -- reason that caused the exception.
    """

    def __init__(self, err_message='', err_cause=None):
        self.message = err_message
        self.cause = err_cause if err_cause is not None else 'UNKNOWN.'


class InputException(StickfixException):
    """
    Exception raised when the arguments passed as input to the bot are incorrect.
    """


class NoStickerException(StickfixException):
    """
    Exception raised when the bot can't find a sticker in a message.
    """


class WrongContextException(StickfixException):
    """
    Exception raised when the bot tries to execute a command from the wrong context.
    For example, this exception should be raised if a command can only be called from a private
    chat and is being
    called from a group chat.
    """


class InsufficientPermissionsException(StickfixException):
    """
    Exception raised when a user tries to call a command without the appropriate permissions.
    """


class Databasexception(StickfixException):
    """
    Exception raised when a database operation fails.
    """
