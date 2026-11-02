"""Characterize the Telegram-to-domain caller identity conversions.

Registered-callback tests already prove how each handler uses these helpers; this module
pins only the conversion contracts themselves: the required form assumes an effective user,
while the optional form maps an absent user to ``None``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from stickfix_domain import UserId
from stickfix_telegram.identity import caller_id, optional_caller_id


def update_from(user_id: int | None) -> SimpleNamespace:
  """Build the minimal update shape the helpers read: ``effective_user.id`` or no user."""
  user = None if user_id is None else SimpleNamespace(id=user_id)
  return SimpleNamespace(effective_user=user)


@pytest.mark.parametrize(
  ("telegram_id", "expected"),
  [(123, UserId(123)), (0, UserId(0))],
  ids=["regular-id", "zero-id"],
)
@pytest.mark.parametrize("convert", [caller_id, optional_caller_id], ids=lambda fn: fn.__name__)
def test_present_effective_user_maps_to_domain_user_id(convert, telegram_id, expected) -> None:
  """Both forms return the numeric Telegram id as a ``UserId``, including a falsy ``0``."""
  assert convert(update_from(telegram_id)) == expected


def test_optional_caller_id_maps_absent_effective_user_to_none() -> None:
  """Anonymous inline traffic reaches the application with no identity."""
  assert optional_caller_id(update_from(None)) is None


def test_caller_id_requires_an_effective_user() -> None:
  """The required form has no missing-user policy: an absent user fails on attribute access."""
  with pytest.raises(AttributeError):
    caller_id(update_from(None))
