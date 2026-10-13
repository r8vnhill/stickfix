# Contributing to Stickfix

Stickfix is a Python 3.14, `uv`-managed workspace. This guide explains how to maintain its
packages, dependency policy, build artifacts, and operational integration without changing
observable Telegram or persistence behavior unintentionally. For basic setup and bot commands,
start with [README.md](README.md).

## Development environment

Use the Python 3.14 toolchain and a version of `uv` compatible with the committed lockfile.
Check the `setup-uv` version in [CI](.github/workflows/ci.yml) and the `uv==` installation in
[Dockerfile](Dockerfile) before changing the toolchain. As inspected on 2026-10-13, both pin
`uv` **0.12.7**. Keep the CI and Docker pins aligned with
`tests/architecture/package_contract_support.py` when upgrading the toolchain.

```bash
uv python pin 3.14
uv lock --check
uv sync --all-packages --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

`uv sync` installs the default `dev` dependency group. This is appropriate for maintainers;
it is not the intended runtime-only container environment. To format deliberately, run
`uv run --locked ruff format .` and review the diff. `ruff.toml` defines the Python 3.14 target,
two-space Python indentation, and 100-column limit. The two-space choice is an explicit
Stickfix decision recorded in Phase C, rather than a general rule for other projects.

If an IDE has locked the checkout's `.venv`, use a disposable external project environment
through `UV_PROJECT_ENVIRONMENT` rather than deleting an in-use directory. Keep temporary
artifacts and coverage files out of version control.

### Testing and coverage

The full pytest suite includes unit, BDD, architecture, and packaging contracts. Targeted
checks are useful during TDD, but final verification must cover the broader suite:

```bash
uv run --locked pytest tests/architecture -v
uv run --locked pytest tests/test_utils/test_logger.py -v
uv run --locked pytest -k logger
uv run --locked pytest
```

The logger scenarios in `tests/features/logger.feature` are exercised by pytest-bdd. Hypothesis
and PyHamcrest remain active tools; preserve their test semantics when updating dependencies.
For local coverage collection, run:

```bash
uv run --locked pytest \
  --cov=bot \
  --cov=stickfix_application \
  --cov=stickfix_domain \
  --cov-report=term-missing
```

Coverage is a local diagnostic; CI has no coverage threshold or report publication contract.
The architecture tests execute separate interpreters for wheel installation and import checks.
A successful subprocess contract does not imply that its execution is counted in ordinary
pytest coverage totals.

## Workspace and packaging verification

### Package ownership and architectural boundaries

The current workspace comprises three independently built distributions:

| Distribution / directory | Import root | Runtime dependencies |
|---|---|---|
| `stickfix-bot` (root) | `bot` | application, domain, third-party |
| `packages/stickfix-application` | `stickfix_application` | `stickfix-domain` |
| `packages/stickfix-domain` | `stickfix_domain` | standard library |

The root distribution also packages the standalone `imghdr.py` compatibility module. Python 3.14
no longer includes `imghdr`, but PTB 13 imports it. `bot.handlers` is currently an implicit
namespace directory (no `__init__.py`), so root setuptools discovery uses
`include = ["bot", "bot.*"]` and `namespaces = true`. Do not change this without a wheel-content
test establishing the replacement topology.

The domain and application are free of Telegram, SQLAlchemy, and runtime infrastructure concerns.
Preserve their package-boundary tests rather than relying on `uv` to prevent invalid imports.
The historical YAML reader is migration-only; PostgreSQL is the runtime persistence backend.

### Authorities and verification commands

Each file has a distinct responsibility. See the [dependency policy](#dependency-policy) for
dependency roles and approved bounds.

| Authority | What it guarantees |
|---|---|
| `pyproject.toml` and member manifests | Requirements, extras, sources, build metadata |
| `uv.lock` | Resolved dependency graph for supported selections |
| `tests/architecture/dependency_policy.py` | Dependency roles, imports, approved bounds |
| `tests/architecture/test_dependency_lock_policy.py` | Root declarations vs. lock metadata |
| `tests/architecture/test_root_distribution.py` | Root wheel contents and isolated installs |
| `tests/architecture/test_package_metadata.py` | Published requirements and wheel contracts |
| `.github/workflows/ci.yml` | CI checks; workflow file is authoritative |
| `Dockerfile` and `docker-compose.yml` | Image, runtime, and database startup |

Use the following sequence before reviewing any change to packaging metadata:

```bash
uv lock --check
uv sync --all-packages --locked
uv run --locked pytest tests/architecture -v
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv build --package stickfix-domain
uv build --package stickfix-application
uv build --package stickfix-bot
```

The Phase A tests build distributions and install the locally built wheels in a temporary,
non-editable environment outside the source checkout. They verify import provenance and
selected locked runtime dependencies. This is stronger than checking imports in the editable
workspace, but it is not a full deployed-bot or PostgreSQL integration test.

Check generated `.whl` contents when changing package discovery, module locations, or resource
ownership. Do not commit the `dist/` directory. A passing wheel build alone does not establish
that all runtime source files or non-Python resources have been included.

### Build isolation and reproducibility

The root manifest declares:

```toml
[build-system]
build-backend = "setuptools.build_meta"
requires = ["setuptools>=66", "wheel>=0.40"]
```

These are **PEP 517/518 build requirements**, not runtime requirements or `dev` group entries.
With build isolation enabled, the build frontend resolves a build environment for the backend.
The declared ranges set minimum versions but permit future releases. The project `uv.lock`
does not by itself freeze those isolated build requirements; even a package named `setuptools`
in `uv.lock` could be present for a different dependency relationship.

Consequently, distinguish the following reproducibility levels:

| Evidence | Supported claim | Not established by this evidence alone |
|---|---|---|
| `uv lock --check` | Lock matches project declarations | Isolated build-backend versions |
| `uv sync --locked` | Selected dependencies match the lock | Identical wheels across builders |
| `uv build --wheel --package ...` | Wheel builds with current tools | Rebuilt artifact may differ |
| Wheel and isolated-import tests | Built modules can be imported | Live bot and database behavior |
| Digest-pinned base | Base-image identity | Other build inputs can change |

Current Docker build steps also run `apt-get upgrade -y`, so package repository state can affect
rebuilds. Neither the project lock nor the pinned base image is a complete guarantee of
byte-for-byte reproducible images.

If stronger build assurance becomes necessary, review and approve a separate change that:

1. Constrains isolated backend versions using the supported `uv` build-constraint mechanism
   (or a dedicated build constraints file), rather than assuming the project lock suffices.
2. Records selected backend versions, artifact hashes, builder version, Python version,
   and build-platform information as provenance.
3. Verifies reproducibility against a clean environment before claiming byte-identical output.
4. Evaluates the impact of system-package snapshots and build-stage dependencies.

Do not silently pin or change `[build-system].requires`, disable build isolation, add a new build
backend, or introduce build constraints as part of a documentation-only change. These require an
approved dependency/build-policy decision and focused artifact verification.

References: [PEP 517](https://peps.python.org/pep-0517/),
[PEP 518](https://peps.python.org/pep-0518/),
[uv build documentation](https://docs.astral.sh/uv/concepts/projects/build/), and
[uv build constraints](https://docs.astral.sh/uv/pip/compile/#adding-build-constraints).

### Environment selection and container boundary

The project declares three distinct dependency surfaces: regular runtime dependencies, the
non-published `dev` group, and published `db`/`graph` extras. Their selection is intentional:

```bash
uv sync --all-packages --locked                 # maintainers: includes dev by default
uv sync --locked --no-dev                       # runtime dependencies, without dev
uv sync --locked --extra db                     # adds pgvector
uv sync --locked --extra graph                  # adds the Neo4j 6.x driver
uv sync --locked --all-extras --no-dev          # runtime plus both published extras
```

`uv run --locked` prevents changes to an out-of-date lockfile but may still synchronize the
project environment. `UV_NO_SYNC=1` disables that environment update at runtime; `UV_OFFLINE=1`
prevents access to package registries. These settings serve different purposes and neither
replaces validation during image construction.

The Docker image copies the root package's runtime sources, installs with
`uv sync --locked --no-dev`, and sets `UV_NO_SYNC=1` after installation. The `container` CI job
builds the image and runs offline checks with networking disabled. The probe in
`tests/architecture/container_smoke.py` verifies imports, Python and dependency versions, and
absence of development or optional-only distributions. CI also checks the Alembic CLI and
Compose configuration. These checks do not contact Telegram or PostgreSQL.

### When packaging ownership changes

Milestone 4.5–4.7 will extract Telegram adapters, move runtime composition into
`stickfix_runtime`, and retire legacy `bot.*` imports. When making these changes, update together:

- workspace member declarations, root dependencies, and `[tool.uv.sources]`;
- `WORKSPACE_GRAPH` and dependency-policy tests;
- setuptools discovery, standalone modules, and packaged resources;
- wheel archive, isolated-install, and container source-copy contracts;
- Docker/Compose commands, Alembic paths, CI, and user-facing documentation.

The help text is currently referenced through a working-directory-relative path. Do not treat
an isolated module-import probe as evidence that every resource lookup works from arbitrary
working directories. Resource relocation belongs to the runtime extraction milestone.

## Optional extras and database verification

SQLAlchemy, psycopg, and Alembic are required by the current runtime and migration workflow.
`pgvector` is optional and is not required by the PostgreSQL runtime repository. The `graph`
extra provides `neo4j>=6,<7`; project code does not currently import Neo4j.

To validate the database workflow using a disposable PostgreSQL instance, configure credentials
locally (never commit them), apply migrations, and then run integration tests:

```bash
docker compose up -d db
# Set STICKFIX_DATABASE_URL to your disposable database connection URL.
uv run --locked alembic upgrade head
uv run --locked alembic check
# Set STICKFIX_TEST_DATABASE_URL to that same disposable database URL.
uv run --locked pytest -m integration
```

`STICKFIX_TEST_DATABASE_URL` explicitly opts into the integration tests. Skipped integration
tests in a normal local suite are not evidence of successful PostgreSQL verification.

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

## Dependency change workflow

For a dependency addition, removal, upgrade, or declaration-surface change:

1. Record the reason and relevant compatibility decision in the traceability record.
2. Update the correct `pyproject.toml` declaration and the typed dependency policy.
3. Update the protected table in this document when direct declarations change.
4. Run `uv lock` with a targeted upgrade where applicable; never upgrade the entire graph
   unintentionally.
5. Review changes in all member manifests and `uv.lock`; commit them together when changed.
6. Run the focused policy, lock, boundary, wheel, and full test suites.
7. Verify the impacted optional selection, or PostgreSQL integration, where relevant.

Changing TOML comments or documentation alone does not require regenerating `uv.lock`.
A change to `[build-system].requires` needs an additional isolated-build review: the runtime
lockfile alone does not establish the exact builder resolution.

## CI and operational verification

The current `.github/workflows/ci.yml` has:

| Job | Current responsibility |
|---|---|
| `quality` | Python 3.14, uv 0.12.7, locked checks, Ruff, pytest, and three wheel builds |
| `postgres-contract` | PostgreSQL 18.6, Alembic upgrade/check, integration tests |
| `container` | Image build, offline smoke checks, Alembic CLI, and Compose validation |

The `quality` job runs `uv lock --check`, locked workspace sync, Ruff, pytest, and package builds.
All `uv run` checks use `--locked`. The `container` job verifies the runtime image with
networking disabled; the `postgres-contract` job verifies migrations and repository integration
against a disposable database. See the workflow for exact steps and current status.

The dependency lock and digest-pinned base image improve repeatability, but do not guarantee
byte-for-byte identical images: system package upgrades and isolated build requirements can
resolve differently over time.

Check static architecture assertions locally, but use actual GitHub Actions results for CI
success claims. Verify runtime deployment independently from repository-only import tests.
When modifying `Dockerfile` or `docker-compose.yml`, preserve the documented bot entrypoint,
PostgreSQL health dependency, and one-shot migration semantics unless a maintainer approves a
behavior change.

## Legacy migration and secrets

The restricted YAML reader and `PostgresMigrationGateway` in
`bot.infrastructure.migration` are for one-shot historical import only; they are not the
runtime storage backend. Historical YAML is converted to migration records without
instantiating current domain objects.

Never commit `.env`, Telegram tokens, `secret.yml`, database passwords, or generated runtime
logs. Old `requirements.txt`/`venv` instructions are deprecated; use the workspace and
`uv` commands above. Consult the traceability plan before retiring any legacy import or
command: removal is scheduled under Milestone 4, not part of routine dependency maintenance.
