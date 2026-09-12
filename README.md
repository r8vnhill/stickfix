# Stickfix

![BSD 2-Clause License](https://img.shields.io/badge/license-BSD%202--Clause-blue)

This work is licensed under the
[BSD 2-Clause "Simplified" License](https://opensource.org/licenses/BSD-2-Clause).

**StickfixBot** is a Telegram bot that lets you tag, store, and retrieve stickers more easily.
You can find it at https://t.me/stickfixbot or on Telegram as `@stickfixbot`.

**Core workflow**: Reply to a sticker with `/add` to tag and save it, then retrieve
matching stickers later with `/get` or via inline queries.

This bot is built with
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
and uses [uv](https://docs.astral.sh/uv) for dependency management.

## Quick start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/r8vnhill/stickfix.git
   cd stickfix
   ```

2. **Create an environment file** from `.env.example` (never commit `.env`):
   ```bash
   Copy-Item .env.example .env
   # Set STICKFIX_TOKEN and POSTGRES_PASSWORD in .env
   ```
   Obtain your token from [@BotFather](https://t.me/botfather) on Telegram by sending `/newbot`.

3. **Start PostgreSQL, apply migrations, and run**:
   ```bash
   docker compose up --build
   ```

PostgreSQL is the runtime backend. The `migrate` service applies Alembic migrations
before the bot starts; application mutations are committed immediately.

## Core commands

- `/add <tags...>` — Reply to a sticker to save it with one or more tags
- `/get <tags...>` — Retrieve stickers matching all specified tags
- `/deleteFrom <tags...>` — Remove a sticker/tag association
- `/setMode <public|private>` — Change whether new stickers are stored publicly or privately
- `/shuffle <on|off>` — Toggle random ordering of results
- `/deleteMe` — Remove your stored data and user account
- `/help` — Show usage instructions in Telegram

## Running the Bot

### Prerequisites

**Python 3.14 or newer** — Verify with `python --version` or install via
[python.org](https://www.python.org/).

**uv** — Install globally: `python -m pip install --user uv` or follow
[uv installation docs](https://docs.astral.sh/uv).

**Telegram Bot Token** — Obtain from [@BotFather](https://t.me/botfather) on Telegram
by sending `/newbot` and following the prompts.

### Setup details

1. **Configure the runtime environment** using `.env.example`. The required values are
   `STICKFIX_TOKEN`, `POSTGRES_PASSWORD`, and (when running outside Compose)
   `STICKFIX_DATABASE_URL`.

### Running

Start the database and bot with:
```bash
docker compose up --build
```

On startup, the bot will:
- Use PostgreSQL for sticker storage
- Create `logs/stickfix.log` for application logs
- Listen for commands and inline queries on Telegram

Press `Ctrl+C` to stop the bot gracefully.

### Verifying the Bot

1. Open Telegram and search for your bot by username
2. Send `/start` or `/help` to see available commands
3. Try adding a sticker with `/add tag1 tag2` (reply to a sticker)
4. Test inline queries by typing `@yourbotusername tag1` in any chat

### Runtime files

The runtime creates and manages:

- `logs/stickfix.log` — Application logs and debug output
- the Docker volume `postgres-data` — PostgreSQL data

Historical YAML files are migration inputs only. Import a copy deliberately with:

```bash
uv run python -m bot.infrastructure.migration.yaml_to_postgres --source data/users.yaml --dry-run
uv run python -m bot.infrastructure.migration.yaml_to_postgres --source data/users.yaml --apply
```

> [!WARNING]
> `.env`, token files, and database credentials must never be committed to version control.

## Architecture

Dependencies point inward only: `handlers → use cases → ports ← infrastructure`.
Domain and application code never import Telegram or SQLAlchemy.

- **Interface** (`bot.handlers`, `bot.stickfix`) — parse Telegram updates, call a
  use case, format replies. No business rules.
- **Application** (`bot.application`) — `requests` (input DTOs), `results` (output
  DTOs), `errors` (Telegram-free failures), `use_cases` (one callable class per
  command), `ports` (outbound `Protocol`s).
- **Domain** (`stickfix_domain`, in `packages/stickfix-domain/`) — `StickfixUser`
  and `StickerPackService` hold sticker/tag rules, pack selection, shuffle, and
  cache behavior. `UserId` is a `NewType("UserId", int)`.
- **Infrastructure** (`bot.infrastructure`) — adapters implementing the ports:
  `persistence.postgres` (runtime), `help` (file provider), and `migration` (the
  one-shot legacy YAML importer, never loaded at runtime).
- Operational logging is configured in `bot.infrastructure.logging`; application
  modules use Python's standard `logging` API without constructing file or
  console handlers. The `stickfix_domain` package never imports `logging`.

Persistence model:

- `UserRepository` handles regular numeric users; the shared public pack has its own
  `PublicPackRepository`. There is no synthetic `SF-PUBLIC` user id in the runtime
  contracts (it survives only inside the legacy YAML reader).
- `PostgresUserRepository` implements both ports and opens one transaction per
  mutation, so a use case that returns success has already committed.
- Migration-only bulk import and full-snapshot verification are owned by
  `PostgresMigrationGateway`; they are not part of the runtime repository ports.
- `/start`, `/add`, `/get`, `/deleteFrom`, `/setMode`, `/shuffle`, `/deleteMe`, and
  inline queries all run through use cases; handlers keep only Telegram concerns.

## Development

### Environment setup

1. Install `uv` globally (e.g., `python -m pip install --user uv` or see
   [uv docs](https://docs.astral.sh/uv)).
2. Run `uv sync` from the repo root to create or refresh the locked virtual
   environment defined by `uv.lock`.
3. When the dependency graph changes, update it with `uv lock` and commit both
   `pyproject.toml` and the regenerated `uv.lock`.

Ensure `uv` is pointing to a Python 3.14 or newer interpreter
(`uv python list`/`uv python use`).

### Common commands

- `uv run ruff check` — run lint rules and formatting checks defined in `ruff.toml`.
- `uv run ruff format` — autoformat files that need cleanup.
- `uv run pytest` — execute the test suite (or pass `-- -k <pattern>` for subsets).
- `uv run python -m bot.stickfix` — run the bot or other scripts inside the locked environment.

### Advanced workflows

For CI/CD configuration, optional database and graph extras, and legacy tooling
migration, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

- **Import errors**: Run `uv sync` to ensure all dependencies are installed.
- **Token errors**: Verify `STICKFIX_TOKEN` matches the token from BotFather.
- **Database errors**: Verify `STICKFIX_DATABASE_URL` and that PostgreSQL is healthy.
- **Bot not responding**: Check `logs/stickfix.log` for error messages.
