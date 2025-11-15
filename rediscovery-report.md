# Rediscovery Report

## Current build & test commands

- `pip install -r requirements.txt` inside a `venv` created manually (this is the legacy script referenced in the repo, but it is now deprecated).
- `python -m bot.stickfix` runs the bot from the activated virtual environment.
- `pytest` is used informally via the `tests/` directory, but it is not wired to a lockfile or consistent environment today.
- Linting/formatting was previously handled by `flake8`, `isort`, and `yapf`, but granularity was brittle and configuration scattered.

## Environment setup

- Developers had to manually select their Python interpreter (3.9 assumed) and keep a local `venv`.
- There was no canonical lockfile, so dependency drift was frequent and onboarding required manual installs of lint/test tooling.

## Architecture notes

- `bot/stickfix.py` creates the Telegram `Updater`, binds the job queue, and registers the handler modules so every incoming command (helper, user, sticker, inline) is routed through the dispatcher.
- Handler modules (`bot/handlers/common.py`, `utility.py`, `stickers.py`, `inline.py`) implement command parsing, context helpers, and inline scoring logic, keeping UI concerns separated from persistence.
- Persistence relies on `bot/database/storage.py`, a YAML-backed `StickfixDB`, with `StickfixUser` objects in `bot/database/users.py` mapping tags to stickers and persisting user preferences such as `shuffle` and `private_mode`.
- Logging comes from `bot/utils/logger.py`, ensuring consistent formatting for lifecycle events (startup, DB saves, request handling).
- The lightweight `tests/` directory exercises this stack, so a stable uv/Ruff workflow will indirectly guarantee handler/storage invariants remain covered.

## Handler/command flows

- `/start` returns a sticker and creates the user record via `HelperHandler`, ensuring every user has a `StickfixUser` entry before saving tags.
- `/help` opens `bot.handlers.common.HELP_PATH` and sends the shared instructions text so helpers stay consistent.
- `/deleteMe` removes the caller from `StickfixDB`; `/setMode <private|public>` flips `private_mode`, and `/shuffle <on|off>` toggles the shuffle flag, all handled inside `UserHandler`.
- `/add <tag...>` expects a reply-to sticker, validates it, and saves tag-to-sticker mappings either in `SF_PUBLIC` or the caller’s private store depending on privacy (see `StickerHandler.__link_tags`).
- `/get <tag...>` (private chats only) looks up stickers in the user’s private map but falls back to `SF_PUBLIC` before sending cached stickers.
- `/deleteFrom <tag...>` removes the sticker’s tags from the appropriate collection.
- Inline queries split the text into tags, dedupe results via `_get_sticker_list`, optionally shuffle them, and return cached inline stickers; `__on_result` clears the `cached_stickers` buffer after a selection.

## Modernization path

- The project now targets Python 3.14 (see `pyproject.toml`), enabling modern typing and interpreter ergonomics.
- `uv` is the single source of truth for dependency resolution: `uv sync` boots the env, `uv lock` regenerates `uv.lock`, and `uv run <cmd>` executes commands within that env.
- `Ruff` replaces the legacy lint stack and also powers formatting (`uv run ruff format`). The config lives in `ruff.toml`.
- Tests should run via `uv run pytest` to ensure they execute in the locked environment.
- Optional extras (`db`, `graph`, `dev`) allow contributors to install Postgres/Neo4j tooling or dev helpers as needed.

## Next steps (per the modernization plan)

1. Expand the rediscovery report with architecture notes once the code paths are mapped.
2. Draft migration scripts/docs (see issue #12) tied to the new workflow.
3. Update CI (`.github/workflows`) to run `uv sync`, `uv run ruff check`, and `uv run pytest`.
