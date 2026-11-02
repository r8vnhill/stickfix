"""Map Telegram update senders to the domain caller identity.

Handlers call these functions before building application requests, so the
Telegram ``int`` id becomes a ``UserId`` at the adapter boundary. Application
commands that act on a user take the required form; inline requests accept an
anonymous caller and take the optional form.
"""

from stickfix_domain import UserId
from telegram import Update


def caller_id(update: Update) -> UserId:
  """Return the update's effective user as a domain ``UserId``.

  Precondition: ``update.effective_user`` is present. Telegram does not guarantee
  this for every update (channel posts, for example, have no sender), and this
  function applies no missing-user policy: an absent user raises
  ``AttributeError``. Callers that can receive senderless updates must check
  first or use :func:`optional_caller_id`.
  """
  return UserId(int(update.effective_user.id))


def optional_caller_id(update: Update) -> UserId | None:
  """Return the effective user as a ``UserId``, or ``None`` when the update has none."""
  user = update.effective_user
  return UserId(int(user.id)) if user is not None else None
