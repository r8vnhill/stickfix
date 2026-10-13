# Contributing

Use the modern `uv` + `ruff` tooling so every contributor shares the same
environment. The sections below cover local setup, checks, optional extras, and CI.

## Local setup

1. Install `uv` globally (`python -m pip install --user uv`) or see
   [uv docs](https://docs.astral.sh/uv).
2. From the repo root run `uv sync` so the lockfile and the virtual environment are
   aligned. The default `dev` dependency group supplies development tooling.
3. When dependencies change run `uv lock`/`uv sync` and commit both `pyproject.toml` and `uv.lock`.

## Lint & tests

- `ruff.toml` is authoritative for lint and formatting: it targets Python 3.14,
  uses two-space indentation, and sets `line-length = 100`. Run `uv run ruff check`
  to lint, `uv run ruff format` to format, and `uv run ruff format --check` to verify.
- `uv run pytest` runs the unit/handler suite inside the locked env; `-m integration`
  additionally needs a PostgreSQL database (see below).
- Use targeted tests (e.g. `uv run pytest tests/handlers`) when touching command
  flows so handler-level coverage stays fast.
- Add new tests next to the affected modules; keep the handler/command flows and the
  application/domain seams covered.
- For local coverage, use:

  ```bash
  uv run pytest \
    --cov=bot \
    --cov=stickfix_application \
    --cov=stickfix_domain \
    --cov-report=term-missing
  ```

  Coverage has no threshold and is not collected or published by CI.

## Optional extras

### PostgreSQL and migrations

SQLAlchemy, psycopg, and Alembic are regular runtime dependencies. Start a disposable
PostgreSQL instance and apply the schema with:

```bash
docker compose up -d db
$env:STICKFIX_DATABASE_URL = "postgresql+psycopg://stickfix:stickfix-test@localhost:5432/stickfix"
uv run alembic upgrade head
uv run alembic check
```

`pgvector` remains an optional extra and is not required by Stickfix persistence.

### Graph database support

The `graph` extra installs the Neo4j 6.x Python driver (`neo4j`), the only supported
graph driver:
```bash
uv sync --extra graph
```

### Extras versus the development group

Extras (`db`, `graph`) are published optional features: consumers select them with
`stickfix-bot[db]`, and locally with `--extra`. Development tools live in the `dev`
dependency group instead, which `uv sync` includes by default and which is never published.
The two selections are independent, so this installs every extra *and* the dev tools:
```bash
uv sync --all-extras
```
Add `--no-dev` to get a runtime-only environment with every extra.

<!-- dependency-policy:start -->

## Dependency policy

Every declared dependency has one entry in the executable policy at
`tests/architecture/dependency_policy.py`. `tests/architecture/test_dependency_policy.py`
checks that policy against `pyproject.toml`, `uv.lock`, production imports, and this table.
When you add, remove, or move a dependency, update the policy and this table in the same change.

| Dependency | Classification | Declaration surface | Purpose |
|---|---|---|---|
| `stickfix-domain` | internal | `runtime` | Telegram-free user and sticker rules. |
| `stickfix-application` | internal | `runtime` | Transport-agnostic use cases, ports, and DTOs. |
| `python-telegram-bot` | runtime | `runtime` | PTB 13.15 synchronous Telegram framework. |
| `pyyaml` | runtime | `runtime` | Historical YAML import for one-shot PostgreSQL migration. |
| `sqlalchemy` | runtime | `runtime` | PostgreSQL persistence models, sessions, and repositories. |
| `alembic` | runtime | `runtime` | PostgreSQL schema migrations. |
| `psycopg` | runtime | `runtime` | PostgreSQL driver loaded through SQLAlchemy's dialect. |
| `urllib3` | compatibility | `runtime` | PTB 13's Python 3.14 urllib3 fallback. |
| `six` | compatibility | `runtime` | Transitive PTB 13 APScheduler requirement. |
| `tornado` | compatibility | `override` | Patched PTB 13.15 Tornado override for polling. |
| `pgvector` | optional | `extra:db` | Optional database vector support. |
| `neo4j` | optional | `extra:graph` | Optional graph driver; currently unused. |
| `hypothesis` | development | `dev` | Property-based tests. |
| `pyhamcrest` | development | `dev` | Matcher-style test assertions. |
| `pytest` | development | `dev` | Test runner. |
| `pytest-bdd` | development | `dev` | Gherkin scenarios for BDD tests. |
| `pytest-cov` | development | `dev` | Coverage collection. |
| `ruff` | development | `dev` | Linting and formatting. |

Classifications describe why a dependency exists; the declaration surface says where
`pyproject.toml` declares it (`runtime`, `dev`, `extra:<name>`, or the `[tool.uv]` `override`).
Compatibility entries are legacy PTB 13 constraints with an approved version boundary and a
verification test. The Tornado override is replaced only during an approved PTB migration that
demonstrates equivalent behavior and no dependency-security regression.

PTB 13 can fall back to upstream urllib3 1.26.x on Python 3.14 when its vendored copy fails;
APScheduler needs `six` transitively. The Tornado override replaces PTB 13.15's 6.1 pin with
patched 6.x (CVE-2026-31958), which is acceptable while Stickfix starts by polling only.

<!-- dependency-policy:end -->

## Dependency metadata workflow

When the dependency graph changes (new package, extra, or version constraint):

1. Update `pyproject.toml` with your changes
2. Run `uv lock` locally to regenerate the lockfile
3. Review the diff in both `pyproject.toml` and `uv.lock`
4. Commit both files together

This keeps the locked dependency graph reproducible for every contributor and CI job.

## CI guidance

CI jobs should replicate the local commands:

```
uv sync
uv run ruff check
uv run pytest
```

Database changes must include migration and repository-contract coverage. Run the PostgreSQL
contract tests with an explicitly disposable database:

```bash
$env:STICKFIX_TEST_DATABASE_URL = $env:STICKFIX_DATABASE_URL
uv run pytest -m integration
```

Describe any new CI steps in `.github/workflows/`.

## Legacy tooling

The restricted YAML reader and `PostgresMigrationGateway` under
`bot.infrastructure.migration` are for one-shot migration workflows only; they
are not runtime storage adapters. Historical YAML is projected into immutable
migration records and never instantiates live domain objects.

The `requirements.txt` and `venv` setup workflows are deprecated. All contributions
should use the `pyproject.toml` + `uv` + `ruff` workflow to keep the environment
consistent across the team. If you need legacy tooling for a migration, raise it on
the project's discussion board first.
