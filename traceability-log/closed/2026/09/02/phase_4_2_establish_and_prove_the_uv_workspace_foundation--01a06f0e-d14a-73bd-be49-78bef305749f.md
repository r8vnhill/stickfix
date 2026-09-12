# Phase 4.2 — Establish and prove the ``uv`` workspace foundation

## Summary

Convert the current root `stickfix-bot` project into the root of the future `uv`
workspace without moving production modules, changing namespaces, or changing
runtime behavior.

This phase will:

* make the existing root project the initial workspace root and sole package;
* reserve `packages/*` for the package extractions in Phases 4.3–4.5;
* move development tooling from the published `dev` extra into the standardized
  `dev` dependency group;
* remove `uv` and Ruff from published runtime dependencies;
* preserve `db` and `graph` as optional package extras;
* generalize the AST architecture checks so they work independently of repository
  layout and correctly resolve relative imports;
* align local development, CI, Docker, and maintainer documentation;
* prove the distinction between development, runtime, and published package
  dependency surfaces.

No production module moves during this phase.

The existing decisions from Milestone 4 remain authoritative: Python stays
`>=3.14,<4`, setuptools remains the build backend, and `uv` stays pinned to
`0.9.8` for this phase.

---

## Current-state constraints

Current `main` establishes the following baseline:

* the root distribution is `stickfix-bot`;

* production code still lives under `bot.*`;

* Python is `>=3.14,<4`;

* setuptools is the build backend;

* `uv` and Ruff are currently declared as runtime dependencies;

* pytest, pytest-cov, pytest-bdd, pre-commit, Hypothesis, and PyHamcrest are
  currently exposed through the `dev` optional extra;

* `db` and `graph` are published optional extras;

* CI uses `uv sync --extra dev --frozen`;

* Docker and CI both pin `uv` to `0.9.8`;

* Docker already uses `uv sync --frozen --no-dev`;

* the architecture test derives package locations directly from names such as
  `bot.domain` and therefore assumes the current repository layout;

* relative imports are not resolved to their absolute module names by the
  architecture scanner;

* the architecture test still contains project-local `violates` /
  `violations` terminology.

The phase should preserve all existing production semantics while deliberately
changing the developer-facing packaging contract from a `dev` extra to a
dependency group.

---

# Cycle 1 — Characterize the root package and workspace contracts

## Goal

Make the intended package/dependency surfaces executable before changing
`pyproject.toml`.

## Scope

Add focused architecture/package-metadata tests, preferably under
`tests/architecture/`, using `tomllib`.

Characterize:

* root project name;
* Python requirement;
* build backend;
* workspace membership pattern;
* runtime dependencies;
* dependency groups;
* optional extras.

Do not yet introduce abstractions for future inter-package dependency graphs that
have no current consumer.

## Red

Add BDD-style tests equivalent to:

```text
given the root project metadata
when its workspace configuration is inspected
then packages/* is the declared future member pattern
```

```text
given the root package metadata
when published dependency surfaces are inspected
then db and graph remain optional extras
and dev is not a published extra
```

```text
given the root package metadata
when runtime dependencies are inspected
then uv, Ruff, pytest, pytest-cov, pytest-bdd, pre-commit,
Hypothesis, and PyHamcrest are not runtime requirements
```

```text
given the development dependency group
when its requirements are inspected
then it contains the existing test tooling and Ruff
```

Also characterize that:

* `requires-python == ">=3.14,<4"`;
* the backend remains `setuptools.build_meta`.

Use DDT for the dependency-name sets rather than duplicating one test per tool.

## Green

Add only the metadata-loading support required by those tests.

Prefer a simple reusable `load_pyproject(path) -> dict[str, object]` helper.

Do **not** create a general workspace dependency-graph framework yet. The first
real cross-package dependency edge appears in Phase 4.3, which is the appropriate
point to introduce canonical package-name handling if it is actually needed.

## Refactor

Keep metadata assertions expressed in terms of package contracts rather than TOML
ordering or formatting.

Avoid snapshotting the entire `pyproject.toml`.

## Acceptance criteria

* target metadata tests fail on current `main` for the expected reasons;
* tests distinguish runtime dependencies, dependency groups, and optional extras;
* no production source file changes;
* no future package is created merely to satisfy the workspace tests.

## Non-goals

* workspace dependency-edge validation;
* package-name canonicalization infrastructure that has no current consumer;
* distribution building;
* dependency reclassification itself.

## Suggested execution order

First. It provides the executable contract for Cycle 2.

---

# Cycle 2 — Establish the workspace and correct dependency classification

## Goal

Make `stickfix-bot` the root member of a valid workspace while ensuring developer
tooling is no longer part of the published package dependency surface.

## Scope

Update:

```text
pyproject.toml
uv.lock
```

Add:

```toml
[tool.uv.workspace]
members = ["packages/*"]
```

Move the existing development dependencies into:

```toml
[dependency-groups]
dev = [
    ...
]
```

The `dev` group must contain:

* pytest;
* pytest-cov;
* pytest-bdd;
* pre-commit;
* Hypothesis;
* PyHamcrest;
* Ruff.

Remove:

* the `dev` entry from `[project.optional-dependencies]`;
* Ruff from `[project].dependencies`;
* `uv` from `[project].dependencies`.

Keep:

* `db`;
* `graph`;
* every existing constraint for dependencies that remain declared;
* the Tornado override;
* setuptools;
* Python `>=3.14,<4`.

Removing the broad package dependency on `uv` is intentional: `uv` is an
operational tool whose executable version is controlled by CI/Docker, not a
runtime library imported by Stickfix.

## Red

Extend Cycle 1 with the published-artifact contract:

```text
given a wheel built from the root project
when its METADATA is inspected
then QA tooling and uv are absent from Requires-Dist
and dev is absent from Provides-Extra
and db and graph remain published extras
```

The wheel metadata, rather than `uv.lock`, is authoritative for what consumers of
`stickfix-bot` receive.

## Green

Apply the TOML changes and regenerate `uv.lock` once.

Review the resulting lock diff and reject unrelated dependency-version churn.
Moving requirements between dependency surfaces may legitimately change lockfile
structure, but should not opportunistically upgrade packages.

## Refactor

Keep `[dependency-groups].dev` as one group for now.

Do not prematurely split it into `test`, `lint`, `docs`, etc.; the current
workspace does not yet need that additional taxonomy.

## Acceptance criteria

* the root is a valid workspace root and remains its only actual package;
* `packages/*` is reserved for future members without introducing placeholders;
* `uv lock --check` succeeds after regeneration;
* `uv sync --locked` installs the development environment;
* default development sync includes Ruff and the test tooling;
* `uv sync --frozen --no-dev` excludes the `dev` group;
* `db` and `graph` remain optional extras;
* the built wheel publishes neither `dev` nor QA/`uv` runtime requirements;
* there are no unrelated dependency upgrades.

`uv` includes the `dev` dependency group by default, while `--no-dev` excludes it,
so no explicit `--group dev` is required for the normal contributor workflow.

## Non-goals

* creating `stickfix-domain`, `stickfix-application`, or `stickfix-telegram`;
* moving `bot`;
* changing the root package namespace;
* switching to `uv_build`;
* changing the Tornado override;
* upgrading Python or project dependencies.

## Suggested execution order

Second. This is the minimum useful workspace vertical slice.

---

# Cycle 3 — Make architecture checks independent of filesystem topology

## Goal

Ensure architecture enforcement survives the upcoming transition from:

```text
bot/domain/...
```

to layouts such as:

```text
packages/stickfix-domain/src/stickfix_domain/...
```

without weakening any existing dependency rule.

## Scope

Refactor `tests/architecture/test_dependency_boundaries.py` and extract test-only
support only where it reduces duplication.

Represent a scanned package explicitly with both:

```text
import namespace
source root
```

For example:

```text
namespace = bot.domain
source_root = <repository root>
```

and, in a temporary future-layout fixture:

```text
namespace = stickfix_domain
source_root = <tmp>/packages/stickfix-domain/src
```

The scanner must derive module names from that boundary rather than from
repository-relative paths.

## Red

Use temporary source trees to prove:

```text
given the current flat source layout
when Python files are scanned
then importer module names are derived correctly
```

```text
given a src-layout workspace package
when the same scanner is used
then importer module names are derived correctly
```

```text
given nested modules and package __init__.py files
when their imports are scanned
then their fully qualified importer names are correct
```

Add an important missing case:

```text
given a relative import that resolves to a forbidden package
when the architecture rule is evaluated
then the resolved absolute import is reported as a nonconformance
```

Cover forms such as:

```python
from ..infrastructure import something
from .ports import something
```

instead of inspecting only the raw `ast.ImportFrom.module` value.

Diagnostics should identify at least:

* importer;
* imported module;
* source path;
* source line where practical;
* applicable dependency rule.

## Green

Introduce a small explicit boundary type, for example:

```python
@dataclass(frozen=True)
class PackageBoundary:
    namespace: str
    source_root: Path
```

Resolve the package directory from the namespace and source root.

Resolve relative `ImportFrom` nodes against the importing package before applying
forbidden-prefix matching.

Replace project-local terminology:

```text
violates
violations
```

with neutral terminology such as:

```text
matches_forbidden_prefix
nonconformances
```

## Refactor

Separate three responsibilities cleanly:

1. discover Python modules for a `PackageBoundary`;
2. extract normalized import edges from one module;
3. evaluate those edges against architecture rules.

Keep these as test infrastructure, not production abstractions.

Preserve the existing `FORBIDDEN_IMPORTS` rules and the migration-isolation
contract unchanged.

## Acceptance criteria

* existing `bot.domain`, `bot.application`, and `bot.handlers` rules remain green;
* the normal runtime composition still cannot import migration infrastructure;
* temporary current-layout and future-`src` fixtures use the same scanner;
* absolute and relative imports are checked consistently;
* diagnostics identify the importing module and offending edge;
* no project-local `violates` / `violations` identifier remains in the touched
  architecture code;
* production imports are unchanged.

## Non-goals

* changing the dependency graph;
* adding import-linter or another architecture dependency;
* scanning installed distributions;
* enforcing workspace metadata edges before those edges exist.

## Suggested execution order

Third. It can begin once the metadata contract is stable, but should finish before
Phase 4.3 moves the domain.

---

# Cycle 4 — Align CI, Docker, and contributor documentation

## Goal

Make the workspace/dependency model reproducible through every supported
development and operational path.

## Scope

Update:

```text
.github/workflows/ci.yml
AGENTS.md
CONTRIBUTING.md
```

Keep the Docker runtime behavior unchanged, except for any change strictly
required for the new workspace metadata.

### CI

Replace both current:

```bash
uv sync --extra dev --frozen
```

calls with:

```bash
uv sync --locked
```

Do not use `--frozen` as the CI consistency check.

`--frozen` trusts the existing lockfile without checking whether project metadata
has changed; `--locked` fails when `uv.lock` is stale. The latter is therefore the
appropriate merge-gating contract.

Keep:

```text
astral-sh/setup-uv version: 0.9.8
Python 3.14
existing Ruff checks
existing pytest jobs
existing PostgreSQL contract flow
```

### Docker

Keep:

```dockerfile
RUN pip install --no-cache-dir uv==0.9.8
RUN uv sync --frozen --no-dev
CMD ["uv", "run", "python", "-m", "bot"]
```

unchanged.

CI is responsible for proving that the lockfile matches project metadata; the
Docker build can then consume that immutable lockfile.

### Documentation

Change the contributor development path to:

```bash
uv sync
```

Retain optional-extra examples such as:

```bash
uv sync --extra db
uv sync --extra graph
```

Use `uv sync --all-extras` where documentation intends development tooling plus
all published extras.

Remove references to `--extra dev`.

Because `AGENTS.md` is already being edited, also repair the nearby stale
architecture description so it matches current `main`:

* PostgreSQL is runtime persistence;
* historical YAML support is migration-only;
* `bot.infrastructure.persistence` owns runtime persistence adapters;
* `bot.infrastructure.migration` owns historical import/migration infrastructure;
* `bot/database` is no longer part of the project;
* Milestone 4 is the active architectural migration context;
* remove obsolete statements about YAML runtime files and periodic YAML saving.

This avoids knowingly leaving contradictory project taxonomy in maintainer
guidance. Current `CONTRIBUTING.md` already describes PostgreSQL/YAML separation
more accurately and should remain aligned with it.

## Red

Where practical, let the metadata tests from Cycles 1–2 guard the dependency
contract.

Do not add brittle tests that parse prose documentation or GitHub Actions YAML
unless a concrete recurring drift justifies them.

## Green

Apply CI and documentation changes.

## Refactor

Remove duplicated or obsolete setup instructions while keeping contributor
commands short and executable.

Do not redesign the CI job topology during this phase.

## Acceptance criteria

From a clean checkout:

```bash
uv lock --check
uv sync --locked

uv run ruff check
uv run ruff format --check
uv run pytest
```

The PostgreSQL contract path remains green:

```bash
uv run alembic upgrade head
uv run alembic check
uv run pytest -m integration
```

Additionally:

* a fresh runtime-only sync succeeds with `--frozen --no-dev`;
* the root wheel builds successfully and its `METADATA` satisfies Cycle 2;
* the Docker image builds with the existing entrypoint;
* CI and Docker both use `uv` 0.9.8;
* CI no longer refers to `--extra dev`;
* contributor documentation no longer refers to `--extra dev`;
* `AGENTS.md` describes PostgreSQL as runtime persistence and YAML as
  migration-only;
* all existing production behavior and startup contracts remain green.

## Non-goals

* changing the Docker entrypoint;
* redesigning Docker layer caching;
* adding a Docker CI job solely for this phase;
* reorganizing CI jobs;
* changing PostgreSQL or migration behavior;
* rewriting project documentation unrelated to architectural drift.

## Suggested execution order

Last. Update operational consumers only after the package and architecture
contracts they consume are settled.

---

# Phase acceptance criteria

Phase 4.2 is complete when all of the following hold:

### Workspace

* `[tool.uv.workspace]` declares `members = ["packages/*"]`;
* `stickfix-bot` remains the only actual package;
* no placeholder distribution has been introduced;
* one root `uv.lock` remains authoritative.

### Dependency surfaces

* production dependencies no longer include `uv` or Ruff;
* `[dependency-groups].dev` contains existing development tooling plus Ruff;
* no published `dev` extra exists;
* `db` and `graph` remain published extras;
* existing dependency constraints are preserved;
* the lockfile contains no unrelated upgrades.

### Published artifact

* the root wheel builds with setuptools;
* wheel `METADATA` contains no QA tooling or `uv` in `Requires-Dist`;
* wheel `METADATA` does not advertise `dev`;
* `db` and `graph` remain advertised extras.

### Architecture assurance

* architecture scanning accepts explicit namespace/source-root boundaries;
* current flat and future `src` layouts are covered;
* relative imports are resolved before dependency evaluation;
* all existing forbidden-import rules remain effective;
* runtime migration isolation remains effective;
* touched project-local identifiers use neutral `nonconformance` terminology.

### Operations

* `uv lock --check` succeeds;
* CI installs through the default `dev` group using `uv sync --locked`;
* Docker retains `uv==0.9.8`;
* Docker retains `uv sync --frozen --no-dev`;
* the existing `python -m bot` startup contract remains unchanged;
* PostgreSQL integration tests remain green.

### Documentation

* development setup uses the `dev` dependency group implicitly through
  `uv sync`;
* `db` and `graph` extra guidance remains available;
* maintainer documentation reflects the current PostgreSQL-runtime /
  YAML-migration-only architecture.

---

# Explicit non-goals and deferred work

Do not include in Phase 4.2:

* moving any production module;
* creating `stickfix-domain`;
* creating `stickfix-application`;
* creating `stickfix-telegram`;
* introducing `stickfix_runtime`;
* changing `bot.*` imports;
* changing public entrypoints;
* adopting `uv_build`;
* changing setuptools package discovery unless a separate existing packaging
  defect is identified and deliberately scoped;
* changing PTB;
* changing Tornado behavior;
* redesigning persistence or migration;
* adding workspace dependency edges before a second package exists;
* opportunistically upgrading project dependencies.

## Explicit follow-up: `uv` version

Retaining `uv==0.9.8` is useful here because it isolates workspace/package
changes from a build-tool upgrade.

It should nevertheless be recorded as deferred technical debt rather than treated
as the desired long-term version. The current `uv` ecosystem has moved beyond the
0.9 line, including subsequent correctness and security fixes.

Evaluate an upgrade separately after this foundation is green, so any resolver,
lockfile, or workspace-semantic changes can be reviewed independently.

---

# Suggested execution order

```text
Cycle 1 — Metadata contracts
          ↓
Cycle 2 — Workspace + dependency classification
          ↓
Cycle 3 — Layout-independent architecture checks
          ↓
Cycle 4 — CI + Docker assurance + documentation
          ↓
Phase 4.3 — Extract stickfix-domain
```

The minimum useful vertical slice is Cycles 1–2: after those two cycles the
repository is already a valid single-package workspace with correctly separated
development and published dependency surfaces. Cycle 3 then establishes the
architecture-testing infrastructure required before the first physical package
move, and Cycle 4 propagates the settled contract to operational workflows.
