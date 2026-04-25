"""Use case for changing a Stickfix user's public/private mode."""

from __future__ import annotations

from bot.application.errors import InvalidCommandInputError
from bot.application.ports import UserRepository
from bot.application.requests import SetModeCommand
from bot.application.results import AcknowledgementResult
from bot.domain.user import StickfixUser, UserModes


class SetMode:
    """Change one user's storage mode."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def __call__(self, command: SetModeCommand) -> AcknowledgementResult:
        mode = self._validated_mode(command.mode)
        user = self._users.get_user(command.user_id)
        if user is None:
            user = StickfixUser(command.user_id)
        user.private_mode = mode == UserModes.PRIVATE
        self._users.save_user(user)
        return AcknowledgementResult()

    @staticmethod
    def _validated_mode(mode: UserModes | str) -> UserModes:
        try:
            return UserModes(mode)
        except ValueError as error:
            raise InvalidCommandInputError(f"{mode} is not a valid mode.") from error
