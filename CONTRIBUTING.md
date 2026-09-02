# Contributing

Use the modern `uv` + `ruff` tooling so every contributor shares the same
environment. The sections below cover local setup, checks, optional extras, and CI.

## Local setup

1. Install `uv` globally (`python -m pip install --user uv` or see [uv docs](https://docs.astral.sh/uv)).
2. From the repo root run `uv sync --extra dev` so the lockfile and the virtual environment are aligned.
3. When dependencies change run `uv lock`/`uv sync` and commit both `pyproject.toml` and `uv.lock`.

## Lint & tests

- `uv run ruff check` (and optionally `uv run ruff format`) replace the old
  flake8/isort mix. `ruff.toml` sets `line-length = 100`.
- `uv run pytest` runs the unit/handler suite inside the locked env; `-m integration`
  additionally needs a PostgreSQL database (see below).
- Use targeted tests (e.g. `uv run pytest tests/handlers`) when touching command
  flows so handler-level coverage stays fast.
- Add new tests next to the affected modules; keep the handler/command flows and the
  application/domain seams covered.

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

To work with Neo4j drivers:
```bash
uv sync --extra graph
```

### All extras including development tools

For comprehensive dependency graph including testing, type checking, and CI helpers:
```bash
uv sync --extra dev
```

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
uv sync --extra dev
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
