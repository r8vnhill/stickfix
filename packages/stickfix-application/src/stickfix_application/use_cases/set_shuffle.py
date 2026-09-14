"""Use case for changing a user's shuffle preference."""

from __future__ import annotations

from stickfix_domain import StickfixUser, Switch

from ..errors import InvalidCommandInputError
from ..ports import UserRepository
from ..requests import SetShuffleCommand
from ..results import AcknowledgementResult


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
