# AGENTS.md

## Collaboration Rule

- Never make implementation, architecture, dependency, or workflow decisions on your own.
- Always present the relevant alternatives, with tradeoffs, and wait for the maintainer's choice before changing direction.
- If a decision is already explicitly recorded in `README.md`, `CONTRIBUTING.md`, `traceability-log/`, or an issue/task from the maintainer, follow that recorded decision.

## Project Shape

- Stickfix is a Telegram sticker tagging bot built with `python-telegram-bot` 13.x.
- Runtime entry is `Stickfix(token).run()` in `bot/stickfix.py`; local `bot.py` and `secret.yml` are intentionally gitignored and must not be committed.
- The codebase is moving toward a layered architecture:
  - `bot/handlers/` contains Telegram adapters.
  - `bot/application/` contains transport-agnostic request/result DTOs, errors, ports, and use cases.
  - `bot/domain/` contains Telegram-free user/sticker rules.
  - `bot/database/` contains YAML-backed persistence adapters.
- `traceability-log/phase_2_introduce_an_application_layer_and_explicit_ports.md` is the active migration guide. Preserve current bot behavior while moving decisions into application use cases.

## Developer Workflow

- Use `uv` for dependency management. Prefer `uv sync --extra dev` for local development.
- Run checks with:
  - `uv run ruff check`
  - `uv run ruff format` when formatting is needed
  - `uv run pytest`
- When dependencies change, update `pyproject.toml`, run `uv lock`, and commit `uv.lock` with it.
- Avoid generated/runtime directories such as `.venv/`, `venv/`, `.pytest-tmp/`, `.pytest_cache/`, `worktmp/`, `data/`, and `logs/`.

## Codebase Conventions

- Keep application modules free of Telegram imports. `tests/application/test_application_seam.py` verifies this boundary.
- Preserve existing command names, reply wording, YAML wire format, and periodic save behavior unless the maintainer explicitly chooses otherwise.
- Prefer explicit dataclasses and typed application errors over dicts, tuples, or Telegram-coupled control flow.
- Prefer narrow Protocol-based ports, such as `bot/application/ports/user_repository.py`, over broad service objects.
- Keep handlers thin: parse Telegram input, build an application request, call a use case, and translate results/errors back to Telegram responses.

## Testing Notes

- Add or update tests near the affected behavior:
  - application seam/use-case tests under `tests/application/`
  - domain tests under `tests/domain/`
  - storage tests at `tests/test_storage_*.py`
  - handler or command-flow tests near the relevant handler coverage
- Use in-memory fakes for application-layer tests instead of Telegram objects or filesystem/YAML details.
- Treat compatibility quirks called out in the traceability log as deliberate behavior and cover them before changing nearby code.

## Integration Notes

- `data/users.yaml` and `logs/stickfix.log` are runtime files created by the bot.
- `secret.yml` stores the Telegram token locally and must never be committed.
- Optional extras exist for database and graph work (`uv sync --extra db`, `uv sync --extra graph`), but do not introduce or depend on them unless the maintainer chooses that path.
