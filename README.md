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
   ```powershell
   Copy-Item .env.example .env
   # Set STICKFIX_TOKEN and POSTGRES_PASSWORD in .env.
   ```
   Obtain your token from [@BotFather](https://t.me/botfather) on Telegram by sending `/newbot`.

3. **Start PostgreSQL, apply migrations, and run**:
   ```bash
   docker compose up --build
   ```

PostgreSQL is the runtime backend. The `migrate` service applies Alembic migrations
before the bot starts; application mutations are committed immediately.

> [!IMPORTANT]
> The current `main` Docker image has unresolved packaging and runtime synchronization gaps.
> Before relying on a production image, complete the container build/offline checks described
> in [CONTRIBUTING.md](CONTRIBUTING.md#environment-selection-and-container-boundary) and
> the open Phase D traceability plan.

## Core commands

- `/add <tags...>` — Reply to a sticker to save it with one or more tags
- `/get <tags...>` — Retrieve stickers matching all specified tags
- `/deleteFrom <tags...>` — Remove a sticker/tag association
- `/setMode <public|private>` — Change whether new stickers are stored publicly or privately
- `/shuffle <on|off>` — Toggle random ordering of results
- `/deleteMe` — Remove your stored data and user account
- `/help` — Show usage instructions in Telegram

## Running the bot

### Prerequisites

**Python 3.14** — The project currently requires Python `>=3.14,<4`. Verify with
`python --version` or select a managed interpreter with `uv python pin 3.14`.

**uv** — Install using the [official installation instructions](https://docs.astral.sh/uv/).
Check the project's CI/Docker toolchain policy in [CONTRIBUTING.md](CONTRIBUTING.md).

**Telegram bot token** — Obtain from [@BotFather](https://t.me/botfather).

### Setup

Configure `.env.example` for Compose. Required values include `STICKFIX_TOKEN` and
`POSTGRES_PASSWORD`. For non-Compose execution, configure `STICKFIX_DATABASE_URL` to point to
a PostgreSQL database with the required schema.

```bash
docker compose up --build
```

The bot uses PostgreSQL for sticker storage, configures operational logging, and handles
commands and inline queries through Telegram long polling. Press `Ctrl+C` to stop it.

### Verify Telegram behavior

1. Open Telegram and search for the bot by username.
2. Send `/start` or `/help` to see available commands.
3. Reply to a sticker with `/add tag1 tag2`.
4. Try an inline query such as `@yourbotusername tag1` in a chat.

### Runtime files

- `logs/stickfix.log` — Application logs and diagnostic output.
- The Compose `postgres-data` volume — Persistent PostgreSQL data.

Historical YAML files are one-shot migration inputs only. To run the established importer:

```bash
uv run --locked python -m bot.infrastructure.migration.yaml_to_postgres \
  --source data/users.yaml --dry-run
uv run --locked python -m bot.infrastructure.migration.yaml_to_postgres \
  --source data/users.yaml --apply
```

> [!WARNING]
> Never commit `.env`, token files, `secret.yml`, or database credentials.

## Architecture

Dependencies point inward: `handlers → use cases → ports ← infrastructure`.
Domain and application code remain independent of Telegram and SQLAlchemy.

- **Interface** (`bot.handlers`, `bot.stickfix`) — Parse Telegram updates, call use cases,
  and format replies.
- **Application** (`stickfix_application`, in `packages/stickfix-application/`) — Requests,
  results, errors, use cases, and `Protocol`-based ports.
- **Domain** (`stickfix_domain`, in `packages/stickfix-domain/`) — Sticker and tag rules,
  user/pack selection, shuffle behavior, and cache logic.
- **Infrastructure** (`bot.infrastructure`) — PostgreSQL persistence, help-file access,
  logging, and the historical YAML migration adapter.

`PostgresUserRepository` implements the application repository ports and commits mutations
transactionally. Historical YAML migration is separate from normal runtime storage.

## Development

### Environment setup

Use Python 3.14 and the workspace lockfile:

```bash
uv python pin 3.14
uv lock --check
uv sync --all-packages --locked
```

The default `dev` dependency group installs testing and formatting tools. When changing any
dependency declaration, update `uv.lock` with `uv lock` and commit both together.

### Common commands

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked pytest -k logger
```

To select tests by expression, use `uv run --locked pytest -k <pattern>` and replace
`<pattern>` with the expression to match.

To start the bot directly (after configuring a token, database URL, and schema), use the
existing module entrypoint:

```bash
uv run --locked python -m bot
```

Use `uv run --locked python -m bot` as the supported module entrypoint. The `bot.stickfix`
module provides runtime composition and is not a separate command-line entrypoint.

For build-system requirements, the limits of `uv.lock`, wheel verification, CI jobs,
PostgreSQL integration, and the pending workspace migration, consult
[CONTRIBUTING.md](CONTRIBUTING.md#workspace-and-packaging-verification).

## Troubleshooting

- **Import errors**: Run `uv sync --all-packages --locked` and check the selected interpreter.
- **Token errors**: Verify `STICKFIX_TOKEN` matches the BotFather token.
- **Database errors**: Verify `STICKFIX_DATABASE_URL`, PostgreSQL health, and migrations.
- **Bot not responding**: Inspect the configured logs and Telegram polling state.
- **Docker import failures**: Verify the image copies the Python 3.14 `imghdr.py` compatibility
  module and that its runtime-only environment is installed before startup.
