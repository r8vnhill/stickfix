# StickFix Bot - AI Coding Assistant Instructions

## Project Overview
StickFix is a Telegram bot for managing stickers with tags. Built with Python 3 and python-telegram-bot v12.8, it supports both public (shared) and private (per-user) sticker collections, accessible via inline queries and chat commands.

## Architecture

### Core Components
- **`bot/stickfix.py`**: Main bot class (`Stickfix`) that initializes the Updater, Dispatcher, and registers handlers. Sets up a 5-minute auto-save job for the database.
- **`bot/database/`**: YAML-based persistence layer with backup rotation
  - `storage.py`: `StickfixDB` dict-like wrapper managing `data/users.yaml` with automatic `.bak` backups
  - `users.py`: `StickfixUser` model with sticker-to-tags mapping and caching
- **`bot/handlers/`**: Command and inline query handlers inheriting from `StickfixHandler`
  - `stickers.py`: `/add`, `/get`, `/deleteFrom` commands
  - `inline.py`: Inline query handling with pagination (49 results per page)
  - `utility.py`: User management (`/setMode`, `/deleteMe`, `/shuffle`) and help
  - `common.py`: Base handler class with shared utilities

### Key Patterns

#### Public vs Private Mode
- **SF_PUBLIC** (`"SF-PUBLIC"`): Special user ID for shared stickers accessible to all users
- Users default to public mode (stickers stored in `SF_PUBLIC`)
- Private mode stores stickers under user's own ID
- Sticker retrieval logic: always merge user's private stickers with public stickers (`set.union`)

```python
# Pattern used throughout handlers
sf_user = self._user_db[user.id] if user.id in self._user_db else self._user_db[SF_PUBLIC]
effective_user = user if user.private_mode else self._user_db[SF_PUBLIC]
```

#### Database Persistence
- YAML format with double-backup rotation (`_1.bak`, `_2.bak`)
- Auto-save every 5 minutes via JobQueue
- On save failure, attempts recovery from backups in order
- Database is a dict-like structure: `{user_id: StickfixUser}`

#### Handler Registration
Handlers register themselves in `__init__` by adding to dispatcher:
```python
self._dispatcher.add_handler(CommandHandler(Commands.ADD, self.__add_sticker, pass_args=True))
```

#### Sticker Caching
`StickfixUser.cache` stores recent query results. Cleared after sending a sticker via inline query (`__on_result` in `inline.py`).

#### Logging
Custom `StickfixLogger` wrapper: console (DEBUG) + rotating file (INFO, 50KB max). Logs to `logs/stickfix.log`.

## Development Workflows

### Running the Bot
The bot requires a `bot.py` entry point file (gitignored) that imports `Stickfix` and provides a token. Typical structure:
```python
from bot.stickfix import Stickfix
import yaml
with open('secret.yml') as f:
    token = yaml.safe_load(f)['token']
Stickfix(token).run()
```

### Dependencies
Install via `pip install -r requirements.txt`:
- `python-telegram-bot~=12.8` (v12, NOT v13+)
- `coloredlogs~=14.0`, `PyYAML~=5.3.1`
- Dev: `pylint~=2.5.3`, `yapf~=0.30.0`

### Testing
Minimal test coverage in `tests/test_db/` - primarily database instantiation. When adding tests, follow the pattern of testing components in isolation.

## Project-Specific Conventions

### Command Patterns
- Commands check for reply messages when operating on stickers (`check_reply`)
- Commands validate sticker presence with `check_sticker`
- Use `get_message_meta(update)` to extract `(message, user, chat)` tuple
- Commands defined in `Commands` enum for consistency

### Error Handling
- Custom exceptions: `NoStickerException`, `WrongContextException`, `InputException`
- Use `raise_*_error()` helpers that log before raising
- Top-level handlers catch all exceptions and call `unexpected_error(e, logger)`
- Gracefully handle user errors with explanatory reply messages

### Context Validation
- `/get` only works in private chats (enforced in handler)
- Inline queries work everywhere
- Commands that modify stickers require reply-to-sticker pattern

### Inline Query Flow
1. Empty query → show help article with random tag suggestion
2. Query with tags → intersection of all tag matches
3. Shuffle if user has `shuffle=True`
4. Paginate with offset (49 results per page)
5. Clear cache on result selection

## File References
- Help text: `bot/utils/HELP.md` (read at runtime)
- Database: `data/users.yaml` (auto-created)
- Logs: `logs/stickfix.log`
- Entry point: `bot.py` (gitignored, create locally with token)

## Important Notes
- Never commit `bot.py`, `secret.yml`, or `data/users.yaml`
- Database format is critical - preserve structure when modifying `StickfixDB`
- python-telegram-bot v12.8 API differs significantly from v13+ (no asyncio)
- When accessing user data, always fall back to `SF_PUBLIC` if user not in DB
- Sticker IDs are Telegram's `file_id` strings, stored in lists per tag
