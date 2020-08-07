""" "Stickfix" (c) by Ignacio Slater M.
    "Stickfix" is licensed under a
    Creative Commons Attribution 4.0 International License.

    You should have received a copy of the license along with this
    work. If not, see <http://creativecommons.org/licenses/by/4.0/>.
"""
from telegram.ext import Updater


class Stickfix:
    """ Base class for @stickfixbot.
        This class implements functions to help manage and store stickers in telegram using chat
        commands and inline queries.
    """
    _updater: Updater

    def __init__(self, token: str):
        self._updater = Updater(token)
