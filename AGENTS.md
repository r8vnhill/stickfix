# AGENTS.md

## Collaboration Rule

- Never make implementation, architecture, dependency, or workflow decisions on your own.
- Always present the relevant alternatives, with tradeoffs, and wait for the maintainer's
  choice before changing direction.
- If a decision is already explicitly recorded in `README.md`, `CONTRIBUTING.md`,
  `traceability-log/`, or an issue/task from the maintainer, follow that recorded decision.

## Project Shape

- Stickfix is a Telegram sticker tagging bot built with `python-telegram-bot` 13.x.
- The runtime entry is `python -m bot`. `bot/__main__.py` loads `bot.config` and runs
  `Stickfix(token, database_url=...)` from `bot/stickfix.py`; the container `CMD` wraps it in
  `uv run`. The local `bot.py` and `secret.yml` are intentionally gitignored and must not be
  committed.
- The codebase is moving toward a layered architecture:
  - `bot/handlers/` contains Telegram adapters.
  - `packages/stickfix-application/` contains transport-agnostic request/result DTOs, errors,
    ports, and use cases in the `stickfix_application` package.
  - `packages/stickfix-domain/` contains Telegram-free user/sticker rules in the
    `stickfix_domain` package.
  - `bot/infrastructure/persistence/` contains PostgreSQL runtime persistence adapters.
  - `bot/infrastructure/migration/` contains the historical YAML import/migration path.
- The active migration guide is the Milestone 4 guide in
  `traceability-log/open/`.
  Preserve current bot behavior while moving package boundaries.

## Developer Workflow

- Use `uv` for dependency management. Prefer `uv sync` for local development; the default
  `dev` dependency group provides development tooling.
- Run the same locked checks as CI (`uv run --locked ruff format .` when formatting is needed):
  - `uv lock --check`
  - `uv sync --all-packages --locked`
  - `uv run --locked ruff check .`
  - `uv run --locked ruff format --check .`
  - `uv run --locked pytest`
- When dependencies change, follow `CONTRIBUTING.md`'s dependency metadata workflow: update
  `pyproject.toml`, the policy in `tests/architecture/dependency_policy.py`, and its documented
  table, then run `uv lock` and commit `uv.lock` in the same change.
- When runtime package contents change (a new top-level module, data file, or source directory),
  keep the `Dockerfile` copying every root-distribution source, and update the wheel and
  container assurance tests (`tests/architecture/test_root_distribution.py`,
  `tests/architecture/test_container_contract.py`). The maintenance checklist in
  `CONTRIBUTING.md` lists the other coupled changes, such as the uv version and workspace members.
- Avoid generated/runtime directories such as `.venv/`, `venv/`, `.pytest-tmp/`,
  `.pytest_cache/`, `worktmp/`, `data/`, and `logs/`.

## Codebase Conventions

- Keep application modules free of Telegram imports.
  `packages/stickfix-application/tests/test_application_seam.py` verifies this boundary.
- Preserve existing command names, reply wording, and historical YAML migration wire
  format unless the maintainer explicitly chooses otherwise.
- Prefer explicit dataclasses and typed application errors over dicts, tuples, or
  Telegram-coupled control flow.
- Prefer narrow Protocol-based ports, such as
  `packages/stickfix-application/src/stickfix_application/ports/user_repository.py`,
  over broad service objects.
- Keep handlers thin: parse Telegram input, build an application request, call a use
  case, and translate results/errors back to Telegram responses.

## Testing Notes

- Add or update tests near the affected behavior:
  - application seam/use-case tests under `packages/stickfix-application/tests/`
  - domain tests under `packages/stickfix-domain/tests/`
  - PostgreSQL repository contracts under `tests/infrastructure/persistence/` (marked
    `integration`; they need `STICKFIX_TEST_DATABASE_URL`)
  - handler or command-flow tests near the relevant handler coverage
  - packaging, dependency, workspace, container, and documentation contracts under
    `tests/architecture/`
- Use in-memory fakes for application-layer tests instead of Telegram objects or
  filesystem/YAML details.
- Treat compatibility quirks called out in the traceability log as deliberate behavior
  and cover them before changing nearby code.

## Integration Notes

- PostgreSQL is runtime persistence; historical YAML is migration-only.
- `logs/stickfix.log` is a runtime file created by the bot.
- `secret.yml` stores the Telegram token locally and must never be committed.
- Optional extras exist for database and graph work (`uv sync --extra db`,
  `uv sync --extra graph`), but do not introduce or depend on them unless the
  maintainer chooses that path.
- The Docker image installs with `uv sync --locked --no-dev` and sets `UV_NO_SYNC=1` so that
  `uv run` never re-syncs at startup. Keep the `CMD` and the Compose commands unchanged until
  Milestone 4.6, and never set `UV_NO_SYNC` for local development.
