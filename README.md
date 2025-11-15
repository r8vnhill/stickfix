# Stickfix

![http://creativecommons.org/licenses/by/4.0/](https://i.creativecommons.org/l/by/4.0/88x31.png)

This work is licensed under a 
[Creative Commons Attribution 4.0 International License](http://creativecommons.org/licenses/by/4.0/)

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
