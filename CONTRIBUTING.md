# Contributing

This guide is for maintainers and contributors. It covers the locked `uv` environment, the
checks CI runs, the packaging and container contracts, and the dependency policy. Everything here
is enforced by tests under `tests/architecture/`. If a rule changes, update the rule, its test,
and this guide in the same change.

## Local setup

1. Install `uv` (`python -m pip install --user uv`, or see the
   [uv docs](https://docs.astral.sh/uv)). CI and the Docker image both use uv 0.12.7.
2. From the repository root, run `uv python pin 3.14` and then `uv sync --all-packages --locked`.
   This creates the development environment, which includes the default `dev` group.
3. Change dependencies only through the
   [dependency metadata workflow](#dependency-metadata-workflow).

## Everyday checks

Run the same locked checks as the CI `quality` job before opening a pull request:

```bash
uv lock --check                         # uv.lock matches every pyproject.toml
uv sync --all-packages --locked         # development environment, default dev group included
uv run --locked ruff check .
uv run --locked ruff format --check .   # `uv run --locked ruff format .` applies formatting
uv run --locked pytest                  # focused: uv run --locked pytest tests/architecture
uv build --package stickfix-domain
uv build --package stickfix-application
uv build --package stickfix-bot
```

`--locked` fails instead of silently rewriting `uv.lock`.

`ruff.toml` controls lint and formatting: Python 3.14, two-space indentation, and
`line-length = 100`. It excludes `traceability-log/`, so historical records keep their original
snippets.

Add tests next to the behavior they cover. When you touch command flows, use focused runs such as
`uv run --locked pytest tests/handlers`. Coverage is available locally and is not collected by CI:

```bash
uv run --locked pytest --cov=bot --cov=stickfix_application --cov=stickfix_domain \
  --cov-report=term-missing
```

## Optional extras

Extras (`db`, `graph`) are published optional features: consumers select them with
`stickfix-bot[db]`, and locally with `--extra`. Development tools live in the `dev` dependency
group instead, which `uv sync` includes by default and which is never published. The two
selections are independent: `uv sync --all-extras` installs every extra *and* the dev tools, and
adding `--no-dev` gives a runtime-only environment with every extra.

- `db` installs `pgvector`. Stickfix persistence does not require it.
- `graph` installs the Neo4j 6.x driver (`neo4j`), the only supported graph driver.

SQLAlchemy, psycopg, and Alembic are regular runtime dependencies. To start a disposable
PostgreSQL instance and apply the schema:

```bash
docker compose up -d db
$env:STICKFIX_DATABASE_URL = "postgresql+psycopg://stickfix:stickfix-test@localhost:5432/stickfix"
uv run --locked alembic upgrade head
uv run --locked alembic check
```

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

When the dependency graph changes (a new package, extra, or version constraint):

1. Update `pyproject.toml`, the policy entry in `tests/architecture/dependency_policy.py`, and
   the [dependency policy](#dependency-policy) table.
2. Run `uv lock`, then review the `pyproject.toml` and `uv.lock` diffs together.
3. Commit both files in the same change. CI's `uv lock --check` and `--locked` steps reject a
   stale lock.

## Workspace and packaging verification

The architecture tests turn the packaging contract into executable checks:

- `test_root_distribution.py` and `test_package_metadata.py`: the three wheels have the expected
  contents and published requirements, and they import after a **non-editable** install into a
  temporary environment outside the checkout.
- `test_workspace_contract.py`: workspace members, locked versions, sources, and internal edges
  match `WORKSPACE_GRAPH`, and CI runs the locked steps in order.
- `test_dependency_policy.py` and `test_dependency_lock_policy.py`: every declaration matches the
  dependency policy and `uv.lock`.
- `test_container_contract.py`: the `Dockerfile` copies every build input, installs with
  `--locked --no-dev`, sets `UV_NO_SYNC=1`, and keeps the Compose services.
- `test_documentation_contract.py`: the commands and facts in these documents stay accurate.

### Development versus deployed environments

Local `uv sync` and `uv run` include the default `dev` group, and `uv run` syncs the environment
automatically before each command. The container installs a runtime-only environment with
`uv sync --locked --no-dev` and then sets `UV_NO_SYNC=1`. As a result, the unchanged
`uv run python -m bot` and `uv run alembic upgrade head` commands use that environment as it is,
instead of re-syncing at startup, which would install the dev tools and need network access.
`UV_NO_SYNC=1` is a container-only safeguard; do not set it for local development.

To reproduce the CI `container` job locally:

```bash
docker build -t stickfix:local .
docker run --rm -i --network none -e UV_OFFLINE=1 stickfix:local \
  uv run python - < tests/architecture/container_smoke.py
docker run --rm --network none -e UV_OFFLINE=1 stickfix:local uv run alembic --version
```

`tests/architecture/container_smoke.py` runs offline, without a token or a database. It checks
the imports, Python 3.14, versions against the image's `uv.lock`, and that no dev-only or
optional-only distribution is installed.

The lockfile makes dependency selection reproducible, but images are not byte-for-byte
reproducible. The base image is digest-pinned, yet the build still runs `apt-get upgrade` and
resolves its build-backend requirements from version ranges.

### Maintenance checklist

- Adding a top-level module, data file, or source directory to `stickfix-bot`: update the
  `Dockerfile` `COPY` lines and `BUILD_INPUTS` in `test_container_contract.py`.
- Adding or extracting a workspace member: update `WORKSPACE_GRAPH` in `dependency_policy.py`,
  `[tool.uv.sources]`, and the CI build steps.
- Upgrading uv: CI and the Dockerfile currently pin uv 0.12.7. Change `setup-uv` in both CI jobs,
  the `Dockerfile` pin, and `UV_VERSION` in `tests/architecture/package_contract_support.py`, all
  in the same commit.
- Refreshing the base image: update the digest in the `Dockerfile`, then rerun the container
  check.
- Changing the startup command (Milestone 4.6): update `CMD`, `DEFAULT_CMD`, the CI `container`
  job, and the README.

## CI

`.github/workflows/ci.yml` is authoritative. It runs three independent jobs:

- `quality`: the everyday checks and the three wheel builds, with `UV_LOCKED=1`.
- `postgres-contract`: runs `alembic upgrade head`, `alembic check`, and `pytest -m integration`
  against a disposable PostgreSQL service.
- `container`: builds the image and runs the offline smoke probe and `alembic --version` with
  `--network none`. It also checks the image's `CMD` and `UV_NO_SYNC=1`, and validates
  `docker compose config`.

Database changes must include migration and repository-contract coverage. Run the PostgreSQL
contract tests locally against an explicitly disposable database:

```bash
$env:STICKFIX_TEST_DATABASE_URL = $env:STICKFIX_DATABASE_URL
uv run --locked pytest -m integration
```

Milestone 4 (phases 4.5–4.7) will still change these contracts deliberately:

- 4.5 extracts the Telegram adapters, which will then own the `imghdr` shim.
- 4.6 retires `bot.*` and changes the startup entrypoint.
- 4.7 aligns Docker, Alembic, and these documents with the final workspace graph.

## Legacy tooling

The restricted YAML reader and `PostgresMigrationGateway` under `bot.infrastructure.migration`
are for one-shot migration workflows only; they are not runtime storage adapters. Historical
YAML is projected into immutable migration records and never instantiates live domain objects.

The `requirements.txt` and `venv` setup workflows are deprecated. Use the `pyproject.toml` +
`uv` + `ruff` workflow so every environment stays consistent. If a migration needs legacy
tooling, raise it on the project's discussion board first.
