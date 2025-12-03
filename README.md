# Stickfix

![BSD 2-Clause License](https://img.shields.io/badge/license-BSD%202--Clause-blue)

This work is licensed under the [BSD 2-Clause "Simplified" License](https://opensource.org/licenses/BSD-2-Clause).

**StickfixBot** is a Telegram bot that let's you link stickers with tags to store them and send them more easily.
You can find it at https://t.me/stickfixbot or as `@stickfixbot` from telegram.

For instructions on how to use the bot, send the command `/help` to the bot from a telegram chat.

This bot is written in Python 3 and uses the 
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) API.

The old `requirements.txt`/`venv` scripts are now deprecated. Modern contributions should rely on the `pyproject.toml` metadata and the `uv`/`Ruff` workflow described below.

## Development

### Environment setup

1. Install `uv` globally (e.g., `python -m pip install --user uv` or see [uv docs](https://docs.astral.sh/uv)).
2. Run `uv sync` from the repo root to create or refresh the locked virtual environment defined by `uv.lock`.
3. When the dependency graph changes, update it with `uv lock` and commit both `pyproject.toml` and the regenerated `uv.lock`.

The project targets **Python 3.14**, so ensure `uv` is pointing to a compatible interpreter (`uv python list`/`uv python use`).

### Common commands

- `uv run ruff check` — run lint rules and formatting checks defined in `ruff.toml`.
- `uv run ruff format` — autoformat files that need cleanup.
- `uv run pytest` — execute the test suite (or pass `-- -k <pattern>` for subsets).
- `uv run python -m bot.stickfix` — run the bot or other scripts through the locked environment.
- `uv run python -m pip install --upgrade --requirement requirements.txt` — legacy compatibility mode, use only when interacting with legacy tooling; prefer the `pyproject` extras for new work.

### Optional extras

Use `uv sync --extra db` to install the PostgreSQL stack (`psycopg`, `pgvector`, `sqlmodel`) or `uv sync --extra graph` for the Neo4j drivers. Add `--extra dev` when working on tests, typing, or CI helpers.

### CI and verification

CI jobs should now run `uv sync`, `uv run ruff check`, and `uv run pytest`, then optionally invoke migration verification scripts. Describe any new steps in `.github/workflows`.

When dependency metadata changes (new package, extra, or constraint fix), run `uv lock` locally or as part of a prow job, review the diff, and commit the updated `pyproject.toml` + `uv.lock`. This keeps the locked graph reproducible for every contributor.

## Running the Bot

### Prerequisites

1. **Python 3.14+** — Verify with `python --version` or install via [python.org](https://www.python.org/).
2. **uv** — Install globally: `python -m pip install --user uv` or follow [uv installation docs](https://docs.astral.sh/uv).
3. **Telegram Bot Token** — Obtain from [@BotFather](https://t.me/botfather) on Telegram:
   - Send `/newbot` and follow the prompts
   - Save the API token provided

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/r8vnhill/stickfix.git
   cd stickfix
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Create a token configuration file** (`secret.yml` — **never commit this**):
   ```yaml
   token: "YOUR_BOT_TOKEN_HERE"
   ```

4. **Create the bot entry point** (`bot.py` — **gitignored**):
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

The bot will:
- Create `data/users.yaml` for sticker storage (auto-backed up every 5 minutes)
- Create `logs/stickfix.log` for logging
- Listen for commands and inline queries on Telegram

Press `Ctrl+C` to stop the bot gracefully.

### Verifying the Bot

1. Open Telegram and search for your bot by username
2. Send `/start` or `/help` to see available commands
3. Try adding a sticker with `/add tag1 tag2` (reply to a sticker)
4. Test inline queries by typing `@yourbotusername tag1` in any chat

### Troubleshooting

- **Import errors**: Run `uv sync` to ensure all dependencies are installed
- **Token errors**: Verify your token in `secret.yml` matches the one from BotFather
- **Permission errors**: Ensure `data/` and `logs/` directories are writable
- **Bot not responding**: Check `logs/stickfix.log` for error messages
