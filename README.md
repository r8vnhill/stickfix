# Stickfix

![BSD 2-Clause License](https://img.shields.io/badge/license-BSD%202--Clause-blue)

This work is licensed under the [BSD 2-Clause "Simplified" License](https://opensource.org/licenses/BSD-2-Clause).

**StickfixBot** is a Telegram bot that lets you tag, store, and retrieve stickers more easily.
You can find it at https://t.me/stickfixbot or on Telegram as `@stickfixbot`.

**Core workflow**: Reply to a sticker with `/add` to tag and save it, then retrieve matching stickers later with `/get` or via inline queries.

This bot is built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) and uses [uv](https://docs.astral.sh/uv) for dependency management.

## Quick start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/r8vnhill/stickfix.git
   cd stickfix
   ```

2. **Create a token configuration file** (`secret.yml` — **never commit this**):
   ```yaml
   token: "YOUR_BOT_TOKEN_HERE"
   ```
   Obtain your token from [@BotFather](https://t.me/botfather) on Telegram by sending `/newbot`.

3. **Install dependencies and run**:
   ```bash
   uv sync
   uv run python bot.py
   ```

The bot will create `data/users.yaml` for storage and `logs/stickfix.log` for logging automatically.

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

**Python 3.14 or newer** — Verify with `python --version` or install via [python.org](https://www.python.org/).

**uv** — Install globally: `python -m pip install --user uv` or follow [uv installation docs](https://docs.astral.sh/uv).

**Telegram Bot Token** — Obtain from [@BotFather](https://t.me/botfather) on Telegram by sending `/newbot` and following the prompts.

### Setup details

1. **Create a local bot entry point** (`bot.py` — **gitignored**):
   ```python
   from bot.stickfix import Stickfix
   import yaml

   with open('secret.yml') as f:
       token = yaml.safe_load(f)['token']

   Stickfix(token).run()
   ```

### Running

Start the bot with:
```bash
uv run python bot.py
```

On startup, the bot will:
- Create `data/users.yaml` for sticker storage (auto-backed up every 5 minutes)
- Create `logs/stickfix.log` for application logs
- Listen for commands and inline queries on Telegram

Press `Ctrl+C` to stop the bot gracefully.

### Verifying the Bot

1. Open Telegram and search for your bot by username
2. Send `/start` or `/help` to see available commands
3. Try adding a sticker with `/add tag1 tag2` (reply to a sticker)
4. Test inline queries by typing `@yourbotusername tag1` in any chat

### Runtime files

When the bot starts, it creates and manages these files in the working directory:

- `data/users.yaml` — All sticker data, backed up automatically every 5 minutes
- `logs/stickfix.log` — Application logs and debug output

> [!WARNING]
> `secret.yml` and any local launcher scripts (like `bot.py`) must never be committed to version control.

## Architecture

Stickfix is organized around a clean-layered architecture with inward-only dependencies:

- **Telegram handlers** and other interface adapters depend on the application layer.
- **Application layer** owns request/result DTOs, application errors, and outbound ports.
- **Domain models** hold sticker and user rules without Telegram-specific concerns.
- **Infrastructure adapters** implement application ports without exposing YAML or filesystem details.

The current architecture introduces an explicit application seam:

- `bot.application.requests` defines transport-agnostic request DTOs.
- `bot.application.results` defines result types for successful application flows.
- `bot.application.errors` defines Telegram-free application failures.
- `bot.application.ports.user_repository.UserRepository` defines the first outbound repository port.

Handlers and runtime wiring currently preserve the existing behavior and YAML persistence model.

## Development

### Environment setup

1. Install `uv` globally (e.g., `python -m pip install --user uv` or see [uv docs](https://docs.astral.sh/uv)).
2. Run `uv sync` from the repo root to create or refresh the locked virtual environment defined by `uv.lock`.
3. When the dependency graph changes, update it with `uv lock` and commit both `pyproject.toml` and the regenerated `uv.lock`.

Ensure `uv` is pointing to a Python 3.14 or newer interpreter (`uv python list`/`uv python use`).

### Common commands

- `uv run ruff check` — run lint rules and formatting checks defined in `ruff.toml`.
- `uv run ruff format` — autoformat files that need cleanup.
- `uv run pytest` — execute the test suite (or pass `-- -k <pattern>` for subsets).
- `uv run python -m bot.stickfix` — run the bot or other scripts inside the locked environment.

### Advanced workflows

For CI/CD configuration, optional database and graph extras, and legacy tooling migration, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

- **Import errors**: Run `uv sync` to ensure all dependencies are installed.
- **Token errors**: Verify your token in `secret.yml` matches the one from BotFather.
- **Permission errors**: Ensure `data/` and `logs/` directories are writable.
- **Bot not responding**: Check `logs/stickfix.log` for error messages.
