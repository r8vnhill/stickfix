"""Use case for deleting a regular user's persisted state."""

from __future__ import annotations

from bot.application.ports import UserRepository
from bot.application.requests import DeleteUserCommand
from bot.application.results import AcknowledgementResult


class DeleteUser:
  """Delete a user if present; absence is intentionally harmless."""

  def __init__(self, users: UserRepository) -> None:
    self._users = users

  def __call__(self, command: DeleteUserCommand) -> AcknowledgementResult:
    deleted = self._users.delete_user(command.user_id)
    return AcknowledgementResult(acknowledged=deleted)
