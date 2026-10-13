# AGENTS.md

## Collaboration rule

- Never make implementation, architecture, dependency, or workflow decisions on your own.
- Present meaningful alternatives and tradeoffs, and wait for the maintainer's choice before
  changing direction. Follow decisions already recorded in repository documents or tasks.
- Preserve the project's externally observable behavior during the ongoing workspace extraction.
- Keep code, comments, and documentation in English unless the maintainer requests otherwise.

## Project shape

- Stickfix is a Telegram sticker tagging bot using `python-telegram-bot` 13.x.
- The supported local entrypoint is `python -m bot`; the runtime facade is
  `Stickfix(token).run()` in `bot/stickfix.py`.
- Local `bot.py`, `secret.yml`, `.env`, and credentials are not tracked.
- The repository is currently a three-distribution `uv` workspace:
  - `stickfix-bot` at the root retains the runtime and Telegram handlers.
  - `stickfix-application` contains transport-neutral DTOs, ports, and use cases.
  - `stickfix-domain` contains transport-neutral user/sticker rules.
- `bot/infrastructure/persistence/` contains PostgreSQL runtime adapters.
- `bot/infrastructure/migration/` owns historical YAML import; it is not runtime storage.
- The Milestone 4 guide under `traceability-log/open/` governs planned extraction of the
  Telegram package, runtime packaging, and removal of legacy `bot.*` imports.

## Development workflow

- Use Python 3.14 and the workspace-managed `uv.lock`.
- Before changing packaging or dependencies, read
  [CONTRIBUTING.md](CONTRIBUTING.md#workspace-and-packaging-verification).
- Use the locked quality sequence:

  ```bash
  uv lock --check
  uv sync --all-packages --locked
  uv run --locked ruff check .
  uv run --locked ruff format --check .
  uv run --locked pytest
  ```

- Use `uv run --locked ruff format .` only when a formatting change is intended.
- When declared dependencies change, update `pyproject.toml`, the typed dependency policy,
  its documented table, and `uv.lock` as applicable; review the resulting graph.
- Do not introduce new build constraints, change build backends, update runtime dependencies,
  or modernize PTB without an explicitly recorded maintainer decision.
- Avoid generated/runtime paths: `.venv/`, `venv/`, `.pytest-tmp/`, `.pytest_cache/`,
  `worktmp/`, `data/`, `logs/`, and `dist/`.

## Package and build contracts

- The root setuptools wheel must package all `bot` modules, including the implicit namespace
  `bot.handlers` (no `__init__.py`), plus standalone `imghdr.py` for PTB 13/Python 3.14.
- Domain and application wheels must remain independently importable without runtime adapters.
- Preserve the package metadata, dependency-policy, architecture, and non-editable installation
  tests under `tests/architecture/`.
- `uv.lock` resolves project dependencies; open PEP 517 `[build-system].requires` bounds do
  not by themselves freeze isolated build backend versions. See the contributor guide's
  "Build isolation and reproducibility" section before making reproducibility claims.
- When package sources or resources move, update Docker build inputs and artifact probes.
  Do not assume a successful editable import proves a complete published wheel or image.
- When package sources or resources change, update the `Dockerfile` inputs and verify
  `tests/architecture/test_root_distribution.py` and
  `tests/architecture/test_container_contract.py`.
- The Docker image uses `UV_NO_SYNC=1` after its locked runtime install. Keep container smoke
  checks offline and preserve the current bot and Alembic entrypoints.

## Codebase conventions

- Keep application modules free of Telegram and persistence implementation imports.
  `packages/stickfix-application/tests/test_application_seam.py` protects this boundary.
- Preserve command names, reply wording, and historical YAML migration formats unless a
  maintainer explicitly chooses a behavior change.
- Prefer explicit dataclasses, typed errors, and narrow Protocol-based ports.
- Keep handlers thin: parse updates, construct requests, invoke use cases, and map results
  back to Telegram responses.
- Follow the documented Stickfix two-space Python indentation convention and Ruff's
  configured rules; it is an explicit project-specific style decision.

## Testing and integration

- Add or update tests adjacent to changed behavior: domain and application tests in their
  respective workspace members, storage tests under `tests/`, handler tests near command flows.
- Prefer in-memory fakes for use cases; use an explicitly disposable PostgreSQL instance
  for integration tests.
- Keep `pytest-bdd` scenarios and existing property-based assertions meaningful; do not
  suppress regressions by weakening generators or skipping tests.
- A skipped database test is not evidence of successful PostgreSQL integration.
- `STICKFIX_TEST_DATABASE_URL` enables database tests. Keep credentials out of commits and logs.
- Treat polling-only transport behavior and the bounded Tornado override as deliberate
  compatibility contracts; retain their verification until an approved PTB migration.
- The existing Docker Compose topology uses PostgreSQL, a one-shot Alembic migration service,
  and a Telegram polling bot. Preserve the current commands until the planned milestone changes.
