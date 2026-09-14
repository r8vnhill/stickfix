# Phase 4.4 — Extract and prove ``stickfix-application``

## Context

Phase 4.3 has already established the workspace pattern that this phase should reuse:

```text
packages/stickfix-domain/
├── pyproject.toml
├── src/stickfix_domain/
└── tests/
```

The repository also already has:

* `[tool.uv.workspace] members = ["packages/*"]`;
* reusable `tomllib` metadata helpers;
* an AST architecture scanner that supports both the current flat `bot.*` layout and arbitrary `src/` roots;
* wheel-content and `METADATA` inspection helpers;
* isolated-wheel installation infrastructure;
* `stickfix-domain` as an independently buildable package;
* root → `stickfix-domain` declared explicitly as a workspace dependency.

Phase 4.4 should extend those mechanisms rather than introduce application-specific alternatives.

The current application implementation remains under:

```text
bot/application/
```

and its public contracts include:

```text
bot.application.__all__
bot.application.ports.__all__
bot.application.use_cases.__all__
```

The application test suite currently lives under `tests/application/`, with application-only repository fakes in
`tests/support/repositories.py`.

One namespace-sensitive behavior also needs explicit preservation: `AddSticker` and `DeleteSticker` currently emit through
the logger names:

```text
bot.application.use_cases.add_sticker
bot.application.use_cases.delete_sticker
```

Existing tests rely on those names, and the runtime configures logging at the parent `bot` logger. The namespace extraction
must therefore preserve those logger identities rather than accidentally changing logging propagation.

---

## Goal

Extract the existing application layer into an independently buildable and installable workspace distribution:

```text
packages/stickfix-application/
├── pyproject.toml
├── src/
│   └── stickfix_application/
└── tests/
```

with this dependency contract:

```text
stickfix-application
    └── stickfix-domain
```

The contract must hold independently at three levels:

```text
source imports
package metadata
built wheel
```

Remove `bot.application` in the same namespace cutover. Do not introduce forwarding modules, import aliases, or a second
authoritative implementation.

Preserve all observable application, Telegram, PostgreSQL, migration, startup, transaction, and logging behavior.

---

# Cycle 4.4.1 — Establish the application package contract

## Goal

Make the intended distribution and dependency edge executable before moving application behavior.

## Scope

Extend the existing repository-level metadata assurance in:

```text
tests/architecture/test_package_metadata.py
tests/architecture/test_dependency_boundaries.py
```

Create only the initial workspace-member scaffold:

```text
packages/stickfix-application/
├── pyproject.toml
└── src/
    └── stickfix_application/
        └── __init__.py
```

Do not duplicate the current implementation into the new package.

## Red

Add BDD-style metadata contracts such as:

```text
given the stickfix-application workspace member
when its project metadata is inspected
then stickfix-domain is its only runtime dependency

given the root stickfix-bot distribution
when its internal runtime dependencies are inspected
then stickfix-application is declared as a direct workspace dependency

given the workspace source configuration
when stickfix-application is resolved
then it resolves to the workspace member rather than an external distribution
```

Assert that `stickfix-application`:

* is named `stickfix-application`;
* uses the same project version as the root distribution;
* uses the same `requires-python` contract as the root;
* retains the existing setuptools backend and `src/` layout;
* declares exactly one runtime dependency by normalized distribution name:
  `stickfix-domain`;
* declares no Telegram, SQLAlchemy, psycopg, Alembic, YAML, or other runtime dependency.

Assert that the root package:

* declares `stickfix-application` directly;
* retains its direct `stickfix-domain` dependency, because the remaining handlers, persistence, and composition code still
  consume domain types directly;
* maps both internal distributions through the existing workspace-source mechanism.

Do not introduce a separate dependency-versioning policy in this phase. Independent package versioning and internal version
bounds remain outside the current milestone.

## Green

Create `packages/stickfix-application/pyproject.toml` following the established `stickfix-domain` package structure.

Add:

```text
stickfix-application
```

to the root runtime dependencies and:

```toml
stickfix-application = { workspace = true }
```

to the root workspace sources.

Regenerate `uv.lock`.

Keep the new Python package empty except for the minimum initializer required by the package scaffold. The legacy
`bot.application` implementation remains authoritative until the atomic cutover in Cycle 4.4.2.

## Refactor

Generalize the existing metadata helpers where doing so removes duplication, for example by allowing workspace-member
metadata to be loaded by distribution directory rather than adding another one-off `application_metadata()` path.

Keep architecture and package-metadata policy at repository level rather than duplicating it inside package-local tests.

## Acceptance criteria

* `stickfix-application` is recognized as a workspace member;
* its declared runtime dependency set is exactly `{stickfix-domain}`;
* root → application and root → domain are explicit workspace edges;
* `uv lock --check` succeeds after regeneration;
* no application production implementation has yet been duplicated;
* the existing runtime and full test suite remain green.

## Non-goals

* moving `bot.application`;
* redesigning DTOs or ports;
* changing use-case behavior;
* changing logging;
* introducing application-specific build tooling;
* independent package versioning;
* Telegram extraction.

## Suggested execution order

First. This creates the physical distribution boundary without creating two application implementations.

---

# Cycle 4.4.2 — Perform the atomic application namespace cutover

## Goal

Move the one authoritative application implementation and its behavior tests to `stickfix_application`, update every
consumer atomically, and remove `bot.application`.

## Scope

Move:

```text
bot/application/__init__.py
bot/application/errors.py
bot/application/requests.py
bot/application/results.py
bot/application/ports/**
bot/application/use_cases/**
```

to:

```text
packages/stickfix-application/src/stickfix_application/
```

Move application-owned tests to:

```text
packages/stickfix-application/tests/
```

Move the application-only in-memory repositories out of the root test-support tree into package-local test support.

Rewire every production and test import that consumes application contracts.

## Red

### Public API characterization

Before completing the cutover, make the intended new namespace authoritative in tests.

Preserve the existing public surfaces exactly:

```python
from stickfix_application import ...
from stickfix_application.requests import ...
from stickfix_application.results import ...
from stickfix_application.ports import ...
from stickfix_application.use_cases import ...
```

Characterize the exact existing:

```text
stickfix_application.__all__
stickfix_application.ports.__all__
stickfix_application.use_cases.__all__
```

rather than merely testing that selected imports happen to work.

Preserve:

* DTO dataclass status;
* DTO field names and defaults;
* enum values;
* error inheritance;
* `@runtime_checkable` repository Protocol behavior;
* use-case constructor signatures;
* callable interfaces;
* result types and fields.

Do not broaden the root package exports while moving them.

### Clean-import seam

Replace the current same-process import seam with a clean-interpreter contract.

Describe it as:

```text
given a fresh Python interpreter containing the application and domain packages
when stickfix_application and its public subpackages are imported
then no Telegram, runtime, persistence, SQLAlchemy, psycopg, or legacy bot module is loaded
```

At minimum inspect loaded top-level namespaces for:

```text
telegram
sqlalchemy
psycopg
alembic
bot
```

This clean process avoids false confidence from modules already present in `sys.modules` during pytest collection.

### Source dependency boundary

Add an application source rule using the existing AST scanner.

Prefer a positive dependency rule:

```text
stdlib
stickfix_application
stickfix_domain
```

rather than maintaining a growing denylist of individual infrastructure libraries.

Therefore, for production code under `stickfix_application`, every absolute import must resolve to:

* Python standard library;
* `stickfix_application`;
* `stickfix_domain`.

This automatically excludes Telegram, SQLAlchemy, psycopg, Alembic, filesystem adapters, root runtime code, and future
unexpected third-party coupling.

Unlike the domain package, standard-library `logging` remains allowed because application use cases currently emit
operational log records.

### Legacy namespace removal

Add an AST contract:

```text
given production Python modules after application extraction
when their import edges are inspected
then none imports bot.application
```

Use the AST scanner rather than raw text search so documentation, historical traceability records, or logger-name strings
do not become false positives.

### Logging compatibility

Retain the existing application logging tests and strengthen them to assert the complete observable record where useful:

```text
logger name
level
message
```

In particular preserve:

```text
bot.application.use_cases.add_sticker
bot.application.use_cases.delete_sticker
```

The package rename alone must not change these logger identities.

## Green

Move the application implementation atomically to:

```text
packages/stickfix-application/src/stickfix_application/
```

Use relative imports for internal application modules where appropriate and use the existing public `stickfix_domain`
surface for domain dependencies.

Update all consumers identified by an import scan, including at least:

```text
bot/handlers/**
bot/stickfix.py
bot/infrastructure/persistence/**
bot/infrastructure/help/**
tests/**
```

where they currently import application contracts.

Do not rely on a manually curated file list as the completeness check; the final AST assertion against
`bot.application` is authoritative.

For the two namespace-sensitive application loggers, do not leave logger identity coupled to the new module `__name__`.
Preserve the existing logger names explicitly so records continue to propagate through the currently configured `bot`
logger hierarchy.

Move:

```text
tests/application/**
```

to:

```text
packages/stickfix-application/tests/**
```

and move the repository fakes currently in:

```text
tests/support/repositories.py
```

into package-local test support, provided the repository-wide reference scan confirms that they remain application-only.

Delete the old support module if no root test consumes it.

Finally delete:

```text
bot/application/
tests/application/
```

in the same cutover.

Do not leave forwarding modules or namespace compatibility imports.

## Refactor

Once the complete suite is green:

* normalize internal application imports;
* preserve intentionally small facade modules rather than promoting implementation helpers into public API;
* remove empty root test-support directories created by the move;
* remove redundant legacy-import assertions superseded by the generic AST boundary;
* keep the application test fakes narrow implementations of the application Protocols.

Update only documentation that would otherwise become immediately incorrect:

```text
README.md
AGENTS.md
ARCHITECTURE-PORTS-ANALYSIS.md
active Milestone 4 traceability record
```

In particular, update `AGENTS.md` references from `bot/application/...` and `tests/application/...` to their new locations.
Broad final-topology documentation and changelog reconciliation remain Phase 4.7 work.

## Acceptance criteria

* `bot/application/` is absent;
* `tests/application/` is absent;
* no production AST import resolves to `bot.application`;
* all application behavior tests execute from `packages/stickfix-application/tests/`;
* package-local tests no longer depend on root `tests.support.repositories`;
* the exact package, ports, and use-case `__all__` surfaces are preserved;
* DTO fields, errors, Protocols, constructor signatures, and callable semantics are unchanged;
* a fresh import of `stickfix_application` loads neither Telegram nor infrastructure libraries;
* application production imports are limited to stdlib, `stickfix_application`, and `stickfix_domain`;
* existing application logger names, levels, and messages remain unchanged;
* handlers still receive application use cases rather than persistence adapters;
* PostgreSQL adapters still implement the same ports;
* existing transaction behavior remains unchanged;
* handler, startup, persistence, migration, and application tests remain green.

## Non-goals

* DTO redesign;
* changing repository Protocols;
* Unit of Work introduction;
* transaction redesign;
* replacing standard-library logging;
* renaming application loggers to `stickfix_application.*`;
* callable-Protocol extraction for Telegram handlers — that remains Phase 4.5;
* persistence extraction;
* runtime namespace extraction.

## Suggested execution order

Second.

The source move, consumer rewiring, test move, and deletion of `bot.application` form one atomic namespace cutover. Splitting
them into separate green states would require either a compatibility shim or duplicate production implementations, both
of which are explicitly excluded.

---

# Cycle 4.4.3 — Prove distribution independence and operational integration

## Goal

Demonstrate that `stickfix-application` is a genuine distribution boundary rather than a package that works only because
the workspace source tree is present.

## Scope

Extend the existing wheel-contract infrastructure from Phase 4.3.

Update the existing CI quality job to build the application package.

No dedicated CI job is needed.

No Dockerfile restructuring should be necessary: the current image already copies the complete `packages/` directory
before `uv sync`. Validate that assumption rather than changing Docker speculatively.

## Red

Add artifact-level BDD contracts:

```text
given the built stickfix-application wheel
when its archive contents are inspected
then it contains stickfix_application and contains no bot.application package

given the built stickfix-application wheel
when its METADATA is inspected
then its only Requires-Dist dependency is stickfix-domain

given locally built domain and application wheels
and an otherwise empty virtual environment
when both wheels are installed without workspace source resolution
then the public application API imports successfully
```

The isolated installation should use the two locally built wheels explicitly and should not obtain an internal Stickfix
package from an index.

Run the import from outside the repository source tree so that a successful import cannot accidentally resolve through the
checkout.

Import at least:

```python
import stickfix_application
import stickfix_application.errors
import stickfix_application.requests
import stickfix_application.results
import stickfix_application.ports
import stickfix_application.use_cases
```

and representative public symbols from the application facade.

Also assert that importing the installed application wheel does not make `telegram`, `sqlalchemy`, `psycopg`, or `bot`
available through accidental packaged content or transitive imports.

## Green

Resolve only packaging or metadata defects exposed by the artifact tests.

Extend the existing CI quality sequence to include:

```bash
uv build --package stickfix-domain
uv build --package stickfix-application
uv build --package stickfix-bot
```

Regenerate and commit `uv.lock` with the package metadata changes.

Do not add a second application-specific workflow.

## Refactor

Generalize the existing wheel-install helper to support installing multiple local wheels if that keeps the domain and
application artifact tests concise.

Prefer one reusable artifact-assurance mechanism that can later support `stickfix-telegram` in Phase 4.5.

Record completion in the Milestone 4 traceability record.

## Acceptance criteria

From a clean checkout:

```bash
uv lock --check
uv sync --all-packages --frozen

uv run ruff check .
uv run ruff format --check .
uv run pytest

uv build --package stickfix-domain
uv build --package stickfix-application
uv build --package stickfix-bot
```

Additionally:

* the existing PostgreSQL contract CI job remains green;
* `stickfix-application` builds as a wheel;
* its wheel contains `stickfix_application` and no legacy `bot.application` package;
* its wheel metadata declares exactly `stickfix-domain` as its runtime dependency;
* domain + application wheels install together in an isolated environment without workspace-source fallback;
* the installed application public API imports successfully;
* the isolated import remains Telegram- and infrastructure-free;
* the root `stickfix-bot` wheel still builds with explicit application and domain dependencies;
* CI builds all workspace packages that exist at the end of this phase;
* no production behavior changes.

## Non-goals

* publishing workspace members independently;
* independent package versioning;
* internal dependency version-bound policy;
* `uv_build`;
* PTB modernization;
* async migration;
* type-checker adoption;
* application API redesign;
* Telegram extraction;
* runtime extraction;
* broad Docker optimization.

## Suggested execution order

Last. This converts source-level separation into evidence that the package boundary also survives build and installation.

---

## Resulting dependency graph

After Phase 4.4:

```text
stickfix-bot
    ├── stickfix-application
    └── stickfix-domain

stickfix-application
    └── stickfix-domain

stickfix-domain
    └── stdlib only
```

The root package continues to own:

```text
bot.handlers
bot.infrastructure
bot.stickfix
bot.config
```

until the later Milestone 4 phases.

---

## Public interface contract

The namespace changes intentionally:

```python
from bot.application import ...
```

becomes:

```python
from stickfix_application import ...
```

Supported subpackage imports become:

```python
from stickfix_application.requests import ...
from stickfix_application.results import ...
from stickfix_application.errors import ...
from stickfix_application.ports import ...
from stickfix_application.use_cases import ...
```

The namespace changes; the exported symbols and their semantics do not.

No `bot.application` compatibility layer is introduced.

---

## Behavior-preservation contract

This phase must not change:

* Telegram command registration or output;
* inline-query behavior;
* DTO shape, defaults, or enum values;
* application error semantics;
* repository Protocol signatures;
* use-case constructor or callable contracts;
* repository selection or save behavior;
* PostgreSQL transaction/commit semantics;
* historical YAML migration behavior;
* application log messages, levels, or logger identities;
* runtime startup behavior;
* public domain APIs.

Any desirable redesign discovered while extracting the package should be recorded as a separate follow-up rather than
folded into Phase 4.4.
