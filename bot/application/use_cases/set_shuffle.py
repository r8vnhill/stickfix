"""Use case for changing a user's shuffle preference."""

from __future__ import annotations

from bot.application.errors import InvalidCommandInputError
from bot.application.ports import UserRepository
from bot.application.requests import SetShuffleCommand
from bot.application.results import AcknowledgementResult
from bot.domain.user import StickfixUser, Switch


class SetShuffle:
    """Create or update a user's shuffle preference."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def __call__(self, command: SetShuffleCommand) -> AcknowledgementResult:
        try:
            switch = Switch(command.shuffle)
        except ValueError as error:
            raise InvalidCommandInputError(f"{command.shuffle} is not a valid switch.") from error

        user = self._users.get_user(command.user_id) or StickfixUser(command.user_id)
        user.shuffle = switch is Switch.ON
        self._users.save_user(user)
        return AcknowledgementResult()
