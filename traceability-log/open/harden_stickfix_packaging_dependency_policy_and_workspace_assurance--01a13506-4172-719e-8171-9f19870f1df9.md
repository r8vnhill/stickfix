# Harden Stickfix packaging, dependency policy, and workspace assurance

## Context

Stickfix `main` has completed Milestone 4 phases 4.1–4.4. The repository currently contains:

- `stickfix-bot`: root distribution containing the remaining `bot.*` runtime and adapters.
- `stickfix-domain`: independent, standard-library-only workspace member.
- `stickfix-application`: independent workspace member depending only on `stickfix-domain`.

Phases 4.5–4.7 will extract Telegram adapters, reorganize the runtime, and retire `bot.*`.

The current root `pyproject.toml` has a package-discovery defect, legacy dependency compatibility constraints, a redundant Neo4j driver dependency, and tooling configuration that does not align with the Python 3.14 baseline.

The goal is to correct and verify the distribution contract while preserving every existing observable behavior.

## Phase A — Restore root distribution correctness [DONE]

**Priority:** Required, before Phase 4.5.

### Goal

Produce a root distribution whose installed wheel contains the complete runtime package and preserves the existing compatibility shim.

### Scope

- `pyproject.toml`
- `tests/architecture/test_package_metadata.py`
- `imghdr.py` (verification only)
- Existing wheel-building test helpers

### Cycle A.1 — Verify complete wheel contents

**Red**

Add a failing BDD-style packaging test:

> Given the current `stickfix-bot` source distribution, when a wheel is built, then the artifact contains every expected runtime Python package, including nested handlers and infrastructure modules.

Assert that:

- `bot/__init__.py` is present.
- `bot/handlers/` is packaged.
- `bot/infrastructure/` and its nested modules are packaged.
- `bot/stickfix.py`, `bot/config.py`, and `bot/__main__.py` are packaged.
- `imghdr.py` is present.
- Repository-only tests, logs, and local data are excluded.

**Green**

Correct setuptools discovery:

```toml
[tool.setuptools]
py-modules = ["imghdr"]

[tool.setuptools.packages.find]
include = ["bot", "bot.*"]
namespaces = false
```

Keep all other packaging behavior unchanged.

**Refactor**

Reuse the existing wheel-archive inspection utilities. Remove redundant discovery exclusions only after the artifact tests demonstrate that doing so does not change the intended contents.

### Cycle A.2 — Verify isolated installation

**Red**

Add an isolated installation contract:

> Given locally built workspace wheels and locked runtime dependencies, when installed into a non-editable environment, then the runtime modules are importable without access to repository source directories.

Verify:

- Importing `bot.stickfix` succeeds.
- Importing representative handler and infrastructure modules succeeds.
- `stickfix_domain` and `stickfix_application` are resolved from their installed distributions.
- The `imghdr` compatibility module retains its characterized behavior.
- The checks do not require a real Telegram token or PostgreSQL server.

Use a temporary working directory outside the source checkout and execute the installed interpreter directly, avoiding accidental success through editable imports.

**Green**

Extend the existing wheel-installation helpers only as necessary.

**Refactor**

Share reusable artifact helpers across the three existing package-contract suites without merging their independent architectural assertions.

### Acceptance criteria

- Root wheel contents conform to the current runtime package topology.
- All three distributions install and import in the tested isolated environment.
- Development dependencies remain absent from published runtime requirements.
- Existing domain/application isolation tests stay green.
- `uv build --package stickfix-bot` succeeds.
- No runtime behavior or public import path changes.

### Non-goals

- Extracting Telegram adapters.
- Replacing setuptools.
- Removing `imghdr`.
- Introducing new entrypoints.
- Changing application behavior.

---

## Phase B — Make dependency policy explicit and verifiable [DONE]

**Priority:** Required assurance and high-value dependency cleanup.

### Goal

Ensure dependencies have a documented purpose, optional feature installations are coherent, and temporary compatibility workarounds cannot regress unnoticed.

### Scope

- `pyproject.toml`
- `uv.lock`
- `tests/test_dependency_policy.py` (relocated to `tests/architecture/`; see outcome)
- `tests/architecture/test_package_metadata.py`
- Relevant dependency documentation

### Cycle B.1 — Characterize runtime and compatibility dependencies

**Red**

Introduce data-driven metadata tests covering:

| Dependency class | Expected contract |
|---|---|
| Runtime | Required by deployed runtime or documented migration operations |
| Development | Not included in published runtime dependencies |
| Internal workspace | Matches the declared dependency graph |
| Compatibility | Has a documented justification and verification |
| Optional | Installs only when its feature is selected |

Verify that the current Telegram dependency range and Tornado override are represented in the dependency policy.

Characterize the distinction between dependencies directly imported by project code and dependencies retained solely for framework compatibility.

**Green**

Make the existing classifications explicit without immediately removing the legacy compatibility constraints.

Preserve `python-telegram-bot` 13.15, its bounded Tornado override, and the documented YAML migration path.

**Refactor**

Consolidate dependency-name normalization and metadata inspection with the existing test utilities.

### Cycle B.2 — Consolidate the Neo4j extra

**Red**

Add a test:

> Given the `graph` optional extra, when the dependency set is resolved, then one supported Neo4j Python driver distribution supplies the import namespace.

Verify that the current graph implementation, if any, does not require deprecated Neo4j 5.x APIs.

**Green**

Subject to maintainer approval, remove `neo4j-driver` and retain `neo4j>=6.0,<7.0`.

Regenerate `uv.lock` and verify optional installation.

**Refactor**

Remove obsolete compatibility documentation or duplicated dependency declarations.

### Cycle B.3 — Protect the Tornado compatibility boundary

**Red**

Extend the existing regression tests:

> Given the PTB 13 compatibility policy, when dependency metadata and the lockfile are inspected, then the resolved Tornado version belongs to the approved patched 6.x range.

Check both the declared override and the locked release.

**Green**

Retain the current override and make its removal condition explicit: replace it only during an approved PTB migration that demonstrates equivalent behavior and no dependency-security regression.

**Refactor**

Avoid duplicating version boundaries across multiple tests where a shared policy definition is practical.

### Acceptance criteria

- Every direct runtime dependency has a documented justification.
- Optional dependency tests pass for `db` and `graph`.
- No overlapping Neo4j distribution remains if consolidation is approved.
- Tornado's existing security regression tests remain green.
- The lockfile is consistent with the dependency declarations.
- Core application behavior is unchanged.

### Non-goals

- PTB 13-to-async migration.
- Moving YAML import support into a new extra.
- Removing established public extras.
- Adding unused graph infrastructure.
- Independently versioning workspace packages.

### Outcome (2026-10-13)

**Maintainer decisions applied:** keep only `neo4j>=6,<7` in `graph`; remove `coloredlogs`;
keep the `urllib3`, `six`, and Tornado constraints; make a typed Python table in test support the
policy's source of truth, mirrored by a human-readable table in `CONTRIBUTING.md`.

**B.1 — Executable policy.**

- `tests/architecture/dependency_policy.py` classifies every declared dependency:
  - classification: internal, runtime, compatibility, development, or optional.
  - declaration surface: `runtime`, `dev`, `extra:<name>`, or `override`.
  - import mode: direct, dynamic, transitive compatibility, or not applicable.
  - justification, plus a verification test for compatibility-sensitive entries.
- `tests/architecture/test_dependency_policy.py` checks the policy against several sources:
  - declarations on each surface.
  - the recorded workspace graph.
  - production import ownership, from an AST scan of `bot/`, `alembic/`, and `packages/*/src`.
  - the cited evidence tests.
  - `uv.lock` root metadata: `requires-dist`, `requires-dev`, the dependency edges, and the
    manifest override.
- `coloredlogs` was declared but never imported. It was removed, and the lock also dropped the now
  orphaned `humanfriendly` and `pyreadline3`.
- `tests/test_dependency_policy.py` was moved with `git mv` to
  `tests/architecture/test_dependency_policy.py`, so it can share the architecture helpers. That
  directory has no `__init__.py` and resolves `conftest` locally.
- The AST scanner was extracted, unchanged, into `tests/architecture/import_graph_support.py`.
- Lockfile parsing now uses one `tomllib` implementation (`lockfile()`,
  `locked_package_versions()`).
- Dev and optional dependency names are derived from the policy instead of hard-coded.

**B.2 — Neo4j.**

- `neo4j-driver` 5.x was removed. It shipped the same `neo4j` import package as `neo4j` 6.x, and
  no project code imports either.
- A data-driven check of locked exports covers the default, `graph`, `db`, and `graph+db`
  selections.
- Smoke installations in a disposable environment confirmed:
  - `--extra graph` installs only `neo4j` 6.0.3.
  - `--extra db` installs `pgvector` 0.4.1 and no `neo4j`.

**B.3 — Compatibility boundaries.**

- PTB, `urllib3`, `six`, and Tornado each carry one `VersionBoundary`. Tests check that the
  declared specifier, the single locked release, and the installed release all fall within it.
- Each compatibility pin is covered by a behavioral test:
  - `urllib3.contrib.appengine` must import.
  - the lock must still record `python-telegram-bot → apscheduler → six`.
  - psycopg must resolve through SQLAlchemy's `postgresql+psycopg` dialect.
- The Tornado entry records the polling-only assumption and the removal condition.
  `tests/test_startup_contract.py` still covers polling-only startup.
- A delimited `CONTRIBUTING.md` table is checked against the policy for:
  - names and surfaces.
  - classification.
  - purpose text.
  A deliberate classification change in the doc made the test fail.

**Verified assumptions.**

- `six` is not imported by project code. It reaches the environment through PTB 13.15 →
  APScheduler 3.6.3, so its direct declaration is a retained bound, not an observed import need.
  This is inferred from the lock graph.
- PTB 13.15 logs that it is "using upstream urllib3" on Python 3.14, which confirms the fallback
  path that the `urllib3` 1.26.x pin supports.

**Evidence.**

- `uv lock --check` passes.
- `ruff check` and `ruff format --check` are clean.
- `pytest`: 197 passed, 3 skipped. The baseline before Phase B was 140 passed, 3 skipped.

---

## Phase C — Align development tooling with Python 3.14

**Priority:** High-value maintenance; schedule independently of active namespace refactors.

### Goal

Use a coherent Python 3.14 tooling baseline with consistent formatting, compatible test dependencies, and explicit lint policy.

### Scope

- `ruff.toml`
- `.editorconfig`
- `[dependency-groups].dev`
- `uv.lock`
- Python source and test formatting
- CI quality checks

### Cycle C.1 — Align Ruff target and formatting

**Red**

Add a configuration contract:

> Given the Python 3.14 project baseline, when repository tooling configuration is inspected, then the language target and indentation policy agree.

Require:

```toml
target-version = "py314"
indent-width = 4
```

**Green**

Update Ruff configuration and apply the minimum formatting changes necessary for repository-wide consistency.

Use the formatter rather than introducing a separate formatting tool.

**Refactor**

Keep the resulting formatting-only changes isolated from semantic changes and package moves.

Review broad unused-import suppressions, including `F401` and `F403`, but retain them until affected source files are characterized.

### Cycle C.2 — Modernize testing dependencies

**Red**

Establish the current baseline for:

- Unit and BDD tests.
- Architecture and package metadata tests.
- Isolated wheel-import tests.
- PostgreSQL integration tests.
- Coverage collection.

**Green**

Evaluate updates in small compatible groups:

1. pytest and pytest-bdd.
2. pytest-cov and its coverage backend.
3. pre-commit and other development utilities where an active use case exists.
4. Compatible Ruff and Hypothesis maintenance releases.

Prefer the latest appropriate stable versions that pass the repository's tests. Do not upgrade every dependency in one unreviewable lockfile change.

**Refactor**

Remove redundant dependency declarations and obsolete workarounds demonstrated unnecessary by tests.

### Acceptance criteria

- Python 3.14 remains the authoritative language baseline.
- Ruff and EditorConfig agree.
- Lint and formatting checks pass.
- BDD scenarios and fixtures retain their behavior.
- Coverage collection works after any approved tooling upgrade.
- No runtime dependency change is introduced through the development group.
- Formatting changes are independently reviewable.

### Non-goals

- New type-checking infrastructure.
- Rewriting tests around a new testing framework.
- Applying newer Python syntax across the repository merely for stylistic reasons.
- Changing domain or application APIs.

---

## Phase D — Close the packaging assurance and reproducibility contract

**Priority:** Required integration verification.

### Goal

Demonstrate that package metadata, workspace resolution, locally built artifacts, CI, and deployment agree about the same dependency graph.

### Scope

- `pyproject.toml` and workspace member metadata
- `uv.lock`
- `.github/workflows/ci.yml`
- `Dockerfile`
- `README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- Relevant traceability records

### Cycle D.1 — Verify the complete workspace

**Red**

Add integration-level checks that independently verify:

- The declared workspace graph matches the actual package graph.
- Package versions and supported Python ranges remain aligned under the existing versioning policy.
- Root and member wheels contain their intended modules.
- Published requirements exclude development dependencies.
- The lockfile is current.
- Non-editable installations are importable.

**Green**

Integrate the focused checks into the existing CI quality job.

Use commands such as:

```bash
uv lock --check
uv sync --all-packages --locked

uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest

uv build --package stickfix-domain
uv build --package stickfix-application
uv build --package stickfix-bot
```

Continue using the existing PostgreSQL CI job for database-dependent integration verification.

Where appropriate, verify installation from built artifacts in a separate environment rather than relying exclusively on editable workspace installations.

**Refactor**

Consolidate repeated CI commands and artifact assertions without introducing a separate build orchestration system.

### Cycle D.2 — Align container and documentation contracts

**Red**

Characterize the current container entrypoint, locked dependency environment, and published package boundaries.

**Green**

Verify that Docker builds the corrected package topology.

Review `--frozen` versus `--locked` according to whether lockfile consistency is checked earlier in the build process.

Preserve the existing startup command until Milestone 4.6 deliberately changes it.

Update documentation to explain:

- Workspace installation and testing.
- Runtime, development, and optional dependency classifications.
- Why Tornado requires an override.
- How to verify installed distributions.
- When to update `uv.lock`.
- Which work is intentionally deferred to Milestone 4.

**Refactor**

Remove outdated documentation and duplicated workflow instructions. Keep the pinned `uv` version synchronized between Docker and CI.

### Acceptance criteria

- Clean-checkout dependency resolution succeeds.
- All existing unit, architecture, BDD, and applicable integration tests pass.
- All existing workspace packages build.
- A non-editable installation passes representative import tests.
- Docker builds and retains the documented polling-only startup behavior.
- CI checks dependency and package consistency before accepting changes.
- Documentation reflects the actual repository topology.
- The traceability record identifies completed changes and remaining decisions.

### Non-goals

- Docker architecture redesign.
- Changing database transaction semantics.
- New deployment infrastructure.
- Independent publication of internal packages.
- Replacing the current build backend.

---

## Suggested execution order

```text
Phase A — Root distribution correctness
    │
    ├── Phase B — Dependency policy
    │
    └── Phase C — Development tooling
              │
              ▼
Phase D — Integration and reproducibility
              │
              ▼
Resume Milestone 4.5–4.7
```

Phase A is the minimum useful vertical slice and should be completed first.

Phase B can proceed after A, while Phase C can be developed independently. Delay applying repository-wide formatting changes if they would create unnecessary conflicts with active Milestone 4 branches.

Phase D integrates the accepted changes and establishes the baseline for subsequent package extractions.

## Maintainer decisions

Before implementation, resolve these choices:

1. **Neo4j:** *Decided 2026-10-13 — retain only the modern driver (done in Phase B).* Retain only the modern driver (recommended), preserve the legacy driver temporarily with a documented compatibility requirement, or defer graph-extra changes.
2. **Test tooling:** Upgrade immediately after distribution correction (recommended if compatibility tests pass), or retain the existing versions until Milestone 4 is complete.
3. **Formatting:** Adopt four-space formatting in an isolated change (recommended), with timing coordinated against package moves.
4. **Build reproducibility:** Retain the current setuptools backend and establish stronger artifact verification first (recommended), evaluating alternative backends only after Milestone 4.
5. **Legacy runtime dependencies:** *Applied in Phase B — compatibility pins kept and verified; unused `coloredlogs` removed by maintainer decision.* Preserve documented compatibility pins until the PTB migration, rather than removing them solely because application code does not import them directly.

## Completion definition

The initiative is complete when:

- The root wheel contains all required runtime modules.
- Every workspace dependency edge conforms to the recorded architecture.
- The root and member distributions pass isolated installation checks.
- Optional extras have coherent and tested dependency graphs.
- Development tooling and configuration are internally consistent.
- Security-related compatibility requirements remain tested.
- The lockfile, CI, Docker, and documentation agree.
- No Telegram command, inline query, persistence, logging, or historical migration behavior has changed.

The completed work should provide a stronger packaging baseline for Milestone 4.5 without prematurely implementing the subsequent architectural migration.