# Contributing

follow the rediscovery plan and use the modern tooling so every contributor shares the same experience.

## Local setup

1. Install `uv` globally (`python -m pip install --user uv` or see [uv docs](https://docs.astral.sh/uv)).
2. From the repo root run `uv sync --extra dev` so the lockfile and the virtual environment are aligned.
3. When dependencies change run `uv lock`/`uv sync` and commit both `pyproject.toml` and `uv.lock`.

## Lint & tests

- `uv run ruff check` (and optionally `uv run ruff format`) replace the flaky/flake8/isort mix.
- `uv run pytest` runs the handler/database tests inside the locked env.
- Use targeted tests (`uv run pytest tests/test_handlers`) when touching command flows so handler-level coverage stays clean.
- Add new tests near the affected modules and keep firm coverage on the handler/command flows summarized in the rediscovery report.

## Optional extras

### Database support

To work with PostgreSQL (`psycopg`, `pgvector`, `sqlmodel`):
```bash
uv sync --extra db
```

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

If you add migration scripts or database tooling, include a job that runs the new scripts (see issue #12) so they stay runnable before deployment.

Describe any new CI steps in `.github/workflows/`.

## Legacy tooling

The `requirements.txt` and `venv` setup workflows are deprecated. All contributions should use the `pyproject.toml` + `uv` + `ruff` workflow to ensure consistency across the team. If you need to interact with legacy tooling for migration purposes, reach out in the project's discussion board.
