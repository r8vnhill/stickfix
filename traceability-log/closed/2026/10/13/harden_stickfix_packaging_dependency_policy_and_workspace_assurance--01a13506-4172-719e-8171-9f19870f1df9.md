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

## Phase C — Align development tooling with Python 3.14 [DONE]

**Status:** Complete as of 2026-10-13.

**Goal:** Upgrade development tooling for Python 3.14 while preserving runtime behavior,
test semantics, architecture contracts, and the runtime dependency graph.

### Maintainer decisions

- Use two-space indentation for Python, matching Ruff's existing setting. This explicit
  project decision overrides the four-space recommendation in general review guidelines;
  it does not change those guidelines for other projects.
- Upgrade dependencies by the groups below and review each lockfile delta before continuing.
- Remove the unused `pre-commit` package without adding replacement hook tooling.
- Validate coverage locally; do not add CI coverage collection, thresholds, or uploads.
- Keep pytest and pytest-bdd, Hypothesis and PyHamcrest, Ruff rules and existing F401/F403
  suppressions. Do not add type checking or broad Python syntax modernization.
- Keep CI's test command and PostgreSQL job topology unchanged. Existing PostgreSQL CI is
  the authority for database integration verification.

### Cycle C.1 — Establish baseline and remove pre-commit

**Baseline evidence, 2026-10-13:** Python 3.14.7, pytest 7.4.4, pytest-bdd 7.3.0,
pytest-cov 4.1.0, coverage 7.11.2, Hypothesis 6.148.0, PyHamcrest 2.1.0, and Ruff 0.14.4.
Collection found 200 tests; the full suite passed 197 with 3 expected skips and two existing
warnings (PTB's upstream urllib3 notice and APScheduler's `pkg_resources` deprecation).
All 85 architecture tests passed. Coverage collection succeeded for `bot`,
`stickfix_application`, and `stickfix_domain` with 79% total coverage and no threshold.
Ruff lint passed and 92 Python files were already formatted. The first Hypothesis logger
property-test run exceeded its deadline during cold startup, then passed on immediate rerun.
The baseline uses an external temporary uv environment because active IDE processes hold
handles in the project's `.venv`; `uv sync --locked` succeeded there.

**Change:** Remove pre-commit from the dev group, executable policy, and contributor table.
Reuse the removed-dependency policy test to ensure it stays absent from declarations and the
lock. Keep other declared development tools unchanged.

**Verification:** The new absence assertion failed before the removal, then the dependency
policy suite passed (59 tests) after lock regeneration. uv removed pre-commit and its
unneeded `cfgv`, `distlib`, `filelock`, `identify`, `nodeenv`, `platformdirs`, and `virtualenv`
packages; unrelated dependencies were retained. The full suite then passed at its baseline:
197 passed, 3 skipped, and the same two existing warnings.

### Cycle C.2 — Upgrade pytest and pytest-bdd together

Review current stable releases and migration notes. Update only their version ranges, upgrade
both with targeted lock operations, and preserve Gherkin scenarios, scenario names, fixture
lifecycle, markers, and test discovery. Verify logger BDD scenarios and the full suite before
continuing.

**Selected versions:** pytest 9.1.1 and pytest-bdd 9.0.0. Logger BDD tests passed (6 tests),
and collection stayed at 200 tests with the same scenario IDs. The first full run had one
known cold-filesystem Hypothesis deadline flake, also observed before the upgrade; the test was
rerun and passed. Its specific fix is recorded in Cycle C.4.

### Cycle C.3 — Upgrade pytest-cov and coverage

Review compatibility and update pytest-cov with its coverage backend as one group. Validate
local collection and reporting for `bot`, `stickfix_application`, and `stickfix_domain`.
Keep coverage data outside tracked files where practical; do not set a percentage threshold or
change CI.

**Selected versions:** pytest-cov 7.1.0 and coverage 7.16.2. The final local coverage run
collected all three packages and reported 79% overall coverage; 198 tests passed, 3 were skipped,
and the two baseline warnings remained.

### Cycle C.4 — Review Hypothesis and PyHamcrest

Evaluate the latest suitable Hypothesis release independently and upgrade it only after its
property tests pass. Review PyHamcrest separately; retain its current release unless a newer
compatible release has a concrete benefit or fixes an observed issue. Preserve generator domains,
property meanings, and matcher assertions.

**Selected versions:** Hypothesis 6.169.0; PyHamcrest remains at 2.1.0 because it is the latest
published release and existing matcher tests pass. The logger property test's first filesystem
operation can exceed Hypothesis's default 200 ms deadline in this environment, including before
Phase C. With maintainer approval, that one test now sets `deadline=None`; its strategy and
assertions are unchanged. The logger and handler suites pass (31 tests).

### Cycle C.5 — Align Ruff and EditorConfig

Set Ruff's target to `py314`, retain `indent-width = 2`, and change Python's EditorConfig
indent size to 2. Preserve line length, lint selections, security exceptions, and F401/F403
suppressions. Upgrade Ruff independently, review formatter and rule changes, and apply only
behavior-preserving formatting. Record the two-space decision above before changing EditorConfig.

**Selected version:** Ruff 0.17.0. Its minimum declared version is now 0.17 so all permitted
versions support the configured target. A small architecture test checks Python target and
indentation agreement. The upgrade exposed one import-order violation in a shared test helper;
that standard-library import was reordered. Ruff lint passes and all 95 Python files are formatted.

### Final verification and acceptance

- Run `uv lock --check`, `uv sync --locked`, Ruff lint and format checks, focused BDD and
  architecture tests, and the full pytest suite after all groups.
- Repeat local coverage collection; require successful reports for the three project packages,
  without a numeric threshold.
- Keep root, domain, and application wheel metadata/content and isolated-installation checks
  passing; verify all three builds.
- Confirm PostgreSQL migrations, schema checks, and integration tests in the existing CI job
  against its configured disposable database. A local skip is not integration evidence.
- Compare test counts, node IDs, skips, xfails, and warnings with the recorded baseline. Explain
  any changes and resolve unexplained regressions before closing Phase C.
- Keep runtime requirements, optional extras, workspace edges, Tornado override, application
  APIs, bot behavior, persistence, and CI topology unchanged.

**Final verification, 2026-10-13:** `uv lock --check` passes. The full suite passes with 198
passed and 3 skipped; the two warnings match the baseline. Local coverage succeeds with 79%
overall and includes all three project packages. Domain, application, and bot distributions
build successfully. A disposable PostgreSQL 18.6 instance applied migrations, passed
`alembic check`, and passed all four integration tests. CI configuration and job topology are
unchanged.

Do not run an unrestricted `uv lock --upgrade`; use targeted package upgrades and review each
complete lockfile diff. Commit dependency declarations and their matching lock together.

---

## Phase D — Close the packaging assurance and reproducibility contract [DONE]

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

### Outcome (2026-10-13) — implemented locally; awaiting the first CI run

Do not mark Phase D `[DONE]` until all three CI jobs (`quality`, `postgres-contract`,
`container`) have passed on GitHub Actions.

**Maintainer decisions:**

- CI and Docker pin uv 0.12.7; `UV_VERSION` in `package_contract_support.py` enforces this.
- The image sets `ENV UV_NO_SYNC=1` after `uv sync --locked --no-dev`. The `CMD` and the Compose
  commands are unchanged.
- A new `container` CI job runs the real build and the offline smoke probe.
- `ruff.toml` excludes `traceability-log`, so ruff 0.17's Markdown formatting doesn't rewrite
  historical snippets. Before this, 9 records already failed `ruff format --check`, which most
  likely made CI `quality` red since the Phase C ruff upgrade.
- `[tool.uv] required-version` was deliberately not added.

**D.1 — Workspace and CI.**

- `test_workspace_contract.py` checks:
  - members against `WORKSPACE_GRAPH` and the lock `[manifest].members`;
  - the locked versions, editable sources, and Python ranges of each member;
  - internal edges: declared, `[tool.uv.sources]`, locked, and editable `requires-dist`.
- It also checks the CI workflow:
  - the order of the quality-job steps, starting with `uv lock --check`;
  - locked execution in the project jobs (`UV_LOCKED=1` and `--locked`);
  - one uv pin across all jobs;
  - the PostgreSQL job's database configuration.
- `ci.yml` was updated to match. `STICKFIX_DATABASE_URL` is now set once at the
  `postgres-contract` job level.

**D.2 — Container: Red evidence (unchanged Dockerfile, uv 0.9.8).**

The image built successfully, and the lock written by uv 0.12.7 parsed under uv 0.9.8. At runtime:

- Running `/app/.venv/bin/python -c "import telegram"` fails with
  `ModuleNotFoundError: No module named 'imghdr'`, raised from `telegram/files/inputfile.py`.
  The image could not start the bot.
- `docker run --network none … uv run python -c "import telegram"` exits with code 1. uv tried to
  download `pytest-9.1.1` because "`stickfix-bot:dev` depends on `pytest`".
- With network, `uv run` reinstalled 18 packages at startup, dev tools included (`pytest`
  importable).

**D.2 — Container: Green.**

- Dockerfile changes: `COPY imghdr.py`, `uv==0.12.7`, `uv sync --locked --no-dev`, then
  `ENV UV_NO_SYNC=1`.
- `test_container_contract.py` statically checks the build inputs (derived from the root
  distribution and `py-modules`), the sync flags and their order, the uv pin, the `CMD`, the
  Compose services, and the `container` job.
- `container_smoke.py` is a stdlib-only probe. It reads expectations from the image's `uv.lock`.
- Local Docker 29.7.2 results:
  - the image builds;
  - the offline smoke probe passes: 6 imports, locked versions, and no dev-only or
    optional-only distributions. It counts 22 installed distributions, matching
    "Installed 22 packages" in the build log. A first run reported 37 because it counted after
    the imports, and APScheduler's `pkg_resources` import adds setuptools' vendored
    distributions to `sys.path`. The probe now counts before importing.
  - after the maintainer-requested refactor (2-space Dockerfile continuations, the base image
    selected through `ARG`, and the top-level files merged into one `COPY`), the image was
    rebuilt and every check above passed again;
  - `uv run alembic --version` prints `alembic 1.19.1` offline;
  - `Cmd` is `["uv","run","python","-m","bot"]` and `Env` contains `UV_NO_SYNC=1`;
  - `docker compose config --quiet` passes with placeholder credentials.

**D.3 — Documentation.**

- README:
  - uses `uv python pin 3.14`, `uv sync --locked`, `uv run --locked pytest -k <pattern>`, and
    `uv run --locked python -m bot`;
  - points to CONTRIBUTING.md for verification.
- CONTRIBUTING.md:
  - adds "Workspace and packaging verification": the locked commands, the non-editable install
    tests, development versus deployed environments, the container smoke check, the
    reproducibility limits, and the uv version policy;
  - describes all three CI jobs;
  - lists the deferred Milestone 4 changes.
- AGENTS.md lists the locked checks and the Dockerfile and assurance-test duties.
- The PTB comment in `pyproject.toml` was moved off the `PyYAML` line.
- `test_documentation_contract.py` guards against the stale commands returning and checks these
  documented facts.

**Local evidence.**

- `uv lock --check` passes.
- `uv sync --all-packages --locked` succeeds.
- `ruff check .` and `ruff format --check .` are clean. Locally this needs
  `--exclude .pytest-tmp --exclude worktmp`, because those directories can't be read on the
  maintainer's machine and ruff 0.17 panics on them. CI doesn't have these directories.
- `pytest`: 252 passed, 3 skipped, including the ruff exclusion contract.
- All three `uv build --package` commands succeed.

**Reproducibility boundary.** Dependency selection is reproducible through `uv.lock`, but images
are not byte-for-byte reproducible. The digest-pinned base still runs `apt-get upgrade -y`, and
the build-backend requirements (`setuptools>=66`, `wheel>=0.40`) are ranges.

**Deferred:**

- Milestone 4.5–4.7:
  - `stickfix-telegram` extraction, which takes ownership of `imghdr`;
  - `bot.*` retirement and the entrypoint change;
  - final alignment of Docker, Alembic, and the docs.
- Possible hardening: system-package snapshot pinning, exact build-backend locking, and provenance.

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
