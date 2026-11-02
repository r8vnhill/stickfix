# `stickfix-telegram`

The Telegram package holds Stickfix's interface adapters: the code that translates
python-telegram-bot updates into application requests and maps results back to
Telegram replies. It is being extracted during Milestone 4.5; for now it contains
only caller identity mapping, and the handlers still live in `bot.handlers`.

## Maintainer contract

- `identity` converts a Telegram update's effective user into a domain `UserId`.
  `caller_id` requires an effective user; `optional_caller_id` returns `None` when
  the update has none.
- The package may import the standard library, `telegram`, `stickfix_domain`, and
  `stickfix_application`. It must not import runtime composition, configuration,
  persistence, or any other infrastructure.
- The package does not ship `imghdr.py`. Importing `telegram` on Python 3.14 still
  depends on the root `stickfix-bot` distribution's compatibility module until
  Milestone 4.5 moves that ownership.

Identity tests live in `tests/`. Handler tests remain under the root `tests/handlers/`
until the handlers move.
