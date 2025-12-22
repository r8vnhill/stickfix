# StickFix Bot - AI Coding Assistant Instructions

## Project Overview
StickFix is a Telegram bot for managing stickers with tags. Built with Python 3.14+ and python-telegram-bot v13+, it supports both public (shared) and private (per-user) sticker collections, accessible via inline queries and chat commands. Uses `uv` for dependency management and `ruff` for code quality.

## Architecture

### Core Components
- **[bot/stickfix.py](bot/stickfix.py)**: Main bot class (`Stickfix`) initializes `Updater`, `Dispatcher`, registers handlers, sets up 5-minute auto-save via `JobQueue`.
- **[bot/database/](bot/database/)**: YAML-based persistence with double-backup rotation
  - [storage.py](bot/database/storage.py): `StickfixDB` (dict subclass) manages `data/users.yaml`; rotates backups to `_1.bak`, `_2.bak` on save
  - [users.py](bot/database/users.py): `StickfixUser` model with sticker tags mapping (`stickers: Dict[str, List[str]]`), caching, and mode toggles (`private_mode`, `shuffle`)
- **[bot/handlers/](bot/handlers/)**: Command/query handlers inherit from `StickfixHandler` base class
  - [stickers.py](bot/handlers/stickers.py): Add/get/delete sticker commands
  - [inline.py](bot/handlers/inline.py): Inline query handler with pagination (49 results/page)
  - [utility.py](bot/handlers/utility.py): User management (`/setMode`, `/deleteMe`, `/shuffle`), help
  - [common.py](bot/handlers/common.py): Base handler with shared utilities (`_get_sticker_list`, `_create_user`)

### Key Patterns

#### Public vs Private Mode
- **SF_PUBLIC** constant: Special user ID (`"SF-PUBLIC"`) for shared stickers accessible to all users
- Default behavior: users store stickers in `SF_PUBLIC` (public mode)
- Private mode: stickers stored under user's own ID, but always merged with public stickers on retrieval
- Retrieval pattern in [common.py#L34-L42](bot/handlers/common.py#L34-L42): intersection of tag matches, union with `SF_PUBLIC`

#### Database Persistence
- YAML format; `StickfixDB` inherits from `dict`, wraps internal `__db` dict
- Auto-save every 300 seconds via `JobQueue.run_repeating()` in [stickfix.py#L35](bot/stickfix.py#L35)
- On save: backs up previous YAML to `_1.bak`, then `_2.bak`; on load error, attempts recovery from backups
- Structure: `{user_id: StickfixUser}` where user_id is int or `"SF-PUBLIC"`

#### Handler Registration
Handlers instantiated in `__setup_handlers()` and self-register with dispatcher in their `__init__`:
```python
# Each handler subclass adds its own command/query handlers to dispatcher
HelperHandler(self.__dispatcher, self.__user_db)
UserHandler(self.__dispatcher, self.__user_db)
StickerHandler(self.__dispatcher, self.__user_db)
InlineHandler(self.__dispatcher, self.__user_db)
```

#### Sticker Caching
`StickfixUser.cached_stickers` (property: `cache`) stores tag→sticker_list mappings from recent queries. Cleared after inline result selection.

#### Logging
`StickfixLogger` wrapper: console DEBUG + rotating file (INFO level). Logs to `logs/stickfix.log`.

## Development Workflows

### Environment Setup
- **Python 3.14+** required; verify with `python --version`
- **uv**: Install globally with `python -m pip install --user uv`
- **Setup**: `uv sync` (or `uv sync --extra dev` for pytest/testing extras)
- **Dependency changes**: Run `uv lock` locally, commit both `pyproject.toml` + `uv.lock`

### Common Commands
- `uv run ruff check` — lint & format checks (defined in `ruff.toml`)
- `uv run ruff format` — auto-format code
- `uv run pytest` — run test suite
- `uv run python -m bot.stickfix` — run bot via locked environment
- `uv run python bot.py` — run bot via entry point (requires local `bot.py` + `secret.yml`)

### Running the Bot
1. Create `secret.yml` (gitignored): `token: "YOUR_BOT_TOKEN"`
2. Create `bot.py` (gitignored) entry point:
   ```python
   from bot.stickfix import Stickfix
   import yaml
   with open('secret.yml') as f:
       token = yaml.safe_load(f)['token']
   Stickfix(token).run()
   ```
3. Run: `uv run python bot.py`; bot creates `data/users.yaml` + `logs/stickfix.log` automatically

### Testing
Tests in [tests/](tests/) use pytest + BDD (pytest-bdd). Test database isolation via fixture (avoid modifying production `users.yaml`).

## Project-Specific Conventions

### Public/Private Mode Logic
- User's sticker retrieval always merges private stickers with `SF_PUBLIC`
- Mode switch doesn't move stickers; it changes where new ones are added
- Inline queries show merged results; `/get` only works in private chats

### Inline Query Flow
1. Empty query → help text with random tag suggestion
2. Query tags → intersection of stickers matching all tags
3. Apply shuffle if `user.shuffle == True`
4. Paginate: 49 results per page, offset via `chosen_inline_result` callback
5. On result select: clear `user.cache[tag]`

### Type Annotations
- Use `StickfixUser`, `StickfixDB`, `CallbackCtx` (type alias for context)
- Handler methods use `CallbackCtx` for type hints

## Critical Files
- **[pyproject.toml](pyproject.toml)**: Dependency metadata; python-telegram-bot>=13.15 (NOT v12), uv, ruff, pytest (optional)
- **[ruff.toml](ruff.toml)**: Linting & formatting rules
- **[bot/utils/HELP.md](bot/utils/HELP.md)**: Help text read at runtime
- **Data**: `data/users.yaml` (auto-created), `logs/stickfix.log`

## Important Notes
- Never commit `bot.py`, `secret.yml`, `data/users.yaml`, or `logs/`
- **Version mismatch**: Old instructions referenced python-telegram-bot v12.8 (blocking/sync API); project now uses v13+ (non-async compatible API, still blocking)
- `StickfixDB` is dict subclass; accessing non-existent keys raises `KeyError` (check with `in` operator first)
- Sticker IDs are Telegram `file_id` strings; stored in lists per tag
- When modifying database structure, preserve `{user_id: StickfixUser}` format; auto-save handles YAML serialization
