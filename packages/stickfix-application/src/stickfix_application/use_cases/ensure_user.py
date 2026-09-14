"""Use case for creating a regular user when `/start` first sees it."""

from __future__ import annotations

from stickfix_domain import StickfixUser

from ..ports import UserRepository
from ..requests import EnsureUserCommand
from ..results import AcknowledgementResult


class EnsureUser:
  """Ensure that one numeric Telegram user has a persisted record."""

  def __init__(self, users: UserRepository) -> None:
    self._users = users

  def __call__(self, command: EnsureUserCommand) -> AcknowledgementResult:
    if self._users.get_user(command.user_id) is None:
      self._users.save_user(StickfixUser(command.user_id))
    return AcknowledgementResult()
