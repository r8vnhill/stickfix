# Phase 4.3 — Extract ``stickfix-domain``

## Goal

Extract the existing domain into an independently buildable and installable `stickfix-domain` workspace distribution under the `stickfix_domain` namespace.

After the phase:

```text
stickfix-domain
    └── stdlib only
```

must be true both in **source imports** and **package metadata**.

The remaining `stickfix-bot` distribution must declare `stickfix-domain` as a direct workspace dependency because its application, Telegram, persistence, and composition code still consume domain types during the intermediate workspace state.

Remove `bot.domain` in the same namespace cutover. Do not introduce forwarding modules, compatibility imports, or a second authoritative copy of the domain implementation.

All observable domain, Telegram, persistence, migration, and startup behavior remains unchanged.

## Prerequisite — Phase 4.2 must be complete

Do not implement 4.3 directly on the current `main`. The repository still has the pre-workspace `pyproject.toml`, including `uv` and Ruff among runtime dependencies and `dev` as an optional extra rather than the planned workspace/dependency-group structure.

Phase 4.3 begins only once Phase 4.2 has established:

```text
[tool.uv.workspace]
members = ["packages/*"]
```

together with:

* reusable `tomllib` metadata helpers;
* architecture-test helpers that accept arbitrary source roots such as `packages/*/src/`;
* the agreed root dependency-group layout;
* one pinned `uv` version across CI and Docker;
* a clean `uv lock --check`;
* no production namespace moves.

This follows the already-recorded Milestone 4 ordering rather than duplicating workspace infrastructure inside the extraction phase.

---

## Cycle 4.3.1 — Establish the package and dependency contracts

### Goal

Make the intended package boundary executable before moving domain behavior.

### Red

Add repository-level metadata and architecture tests using the helpers introduced in Phase 4.2.

Describe the metadata behavior along these lines:

```text
given the stickfix-domain workspace member
when its package metadata is inspected
then it has no runtime dependencies

given the root stickfix-bot package
when its internal dependencies are inspected
then stickfix-domain is declared as a direct workspace dependency

given stickfix-domain source code
when its absolute imports are inspected
then every external import belongs to the Python standard library

given stickfix-domain source code
when effectful imports excluded by the domain contract are inspected
then logging is absent
```

Assert:

* package name is `stickfix-domain`;
* version equals the root project version rather than duplicating a hard-coded `0.1.0` assertion;
* `requires-python` equals the root package requirement already frozen by Phase 4.2;
* build backend is the Phase 4.2 setuptools backend;
* `project.dependencies` is explicitly empty;
* no dependency on any Stickfix package is declared;
* the root distribution declares `stickfix-domain` using the workspace-source convention established by Phase 4.2.

For source architecture, allow:

* relative imports inside `stickfix_domain`;
* absolute `stickfix_domain.*` imports if genuinely needed;
* Python standard-library modules.

Reject:

* all non-stdlib third-party imports;
* all other Stickfix packages or the legacy `bot` namespace;
* `logging`, despite it being stdlib.

This is stronger and less brittle than individually naming Telegram, SQLAlchemy, psycopg, Alembic, YAML, and every future dependency.

Do **not** exclude `random` in this phase. `StickfixUser` currently uses module-level randomness for shuffle and random-tag behavior, and changing that is a domain API/design change rather than a package extraction.

### Green

Create only the workspace-member scaffold:

```text
packages/stickfix-domain/
├── pyproject.toml
└── src/
    └── stickfix_domain/
        └── __init__.py
```

Configure setuptools for the `src/` layout and add the root workspace dependency/source declaration.

Update `uv.lock`.

Do not copy the old implementation into the new package while leaving `bot.domain` authoritative; that would create two sources of truth.

### Refactor

Keep package-metadata assertions expressed through the shared Phase 4.2 helpers. Do not introduce `stickfix-domain`-specific TOML parsing.

### Acceptance criteria

* workspace metadata identifies `stickfix-domain`;
* its runtime dependency set is empty;
* root metadata explicitly contains the root → domain edge;
* the architecture scanner understands the new `src/` root;
* the existing application and runtime remain green because the namespace cutover has not happened yet.

### Non-goals

* moving domain behavior;
* changing domain APIs;
* modernizing typing syntax;
* changing randomness;
* extracting application code.

### Suggested execution order

First. It establishes the physical/package boundary without duplicating production behavior.

---

## Cycle 4.3.2 — Perform the atomic domain namespace cutover

### Goal

Move the one authoritative domain implementation and all of its behavior tests into `stickfix-domain`, then make every production consumer use the new namespace.

### Red

Move or introduce contract tests that describe the new public API:

```python
from stickfix_domain import SF_PUBLIC, StickfixUser, Switch, UserId, UserModes
from stickfix_domain.services import StickerPackService
```

The current package deliberately exports exactly those five root symbols, while the services package deliberately exposes `StickerPackService`. Preserve that contract rather than broadening it during extraction.

Move the existing behavior tests to:

```text
packages/stickfix-domain/tests/
├── test_user.py
└── services/
    └── test_sticker_pack_service.py
```

Change only imports and namespace-sensitive patch targets at this point. In particular:

```python
patch("stickfix_domain.user.random.shuffle", ...)
```

replaces the current `bot.domain.user.random.shuffle` target.

Add an AST-based repository contract:

```text
given production Python modules after the domain extraction
when their imports are inspected
then none imports bot.domain
```

Do not implement this as a raw textual search.

### Green

Move:

```text
bot/domain/__init__.py
    → packages/stickfix-domain/src/stickfix_domain/__init__.py

bot/domain/identifiers.py
    → packages/stickfix-domain/src/stickfix_domain/identifiers.py

bot/domain/user.py
    → packages/stickfix-domain/src/stickfix_domain/user.py

bot/domain/services/
    → packages/stickfix-domain/src/stickfix_domain/services/
```

Use relative imports inside the domain package where appropriate.

Rewire **all** current consumers, including:

* application request DTOs;
* application ports;
* repository/use-case helpers;
* individual use cases;
* PostgreSQL repositories and mappers;
* runtime composition in `bot/stickfix.py`;
* `bot/handlers/common.py`;
* application/infrastructure tests;
* repository fakes and other test support.

The current repository has domain dependencies across application, persistence, handlers, and composition, so the cutover should be driven by an import scan rather than a manually maintained file list.

For code outside `stickfix-domain`, prefer the deliberately exported public API when the symbol is public:

```python
from stickfix_domain import StickfixUser, UserId
from stickfix_domain.services import StickerPackService
```

rather than coupling consumers unnecessarily to `stickfix_domain.user` or `stickfix_domain.identifiers`.

Delete:

```text
bot/domain/
tests/domain/
```

in the same green cutover.

### Refactor

After the entire suite is green:

* remove obsolete import aliases;
* normalize imports around the public package API;
* remove empty directories created by the move;
* ensure `StickerPackMutation` and other implementation details are not accidentally promoted into the public API.

Do not opportunistically rewrite `StickfixUser`, collection types, shuffle semantics, or service APIs.

### Acceptance criteria

* all existing domain behavior tests pass from their package-local location;
* every current consumer imports the new namespace;
* `bot/domain/` is absent;
* no production AST import resolves to `bot.domain`;
* no forwarding package exists;
* the public API remains the explicitly documented set above;
* Telegram and persistence tests remain green.

### Non-goals

* immutable domain redesign;
* RNG injection;
* new domain types;
* PBT or mutation-testing expansion;
* changes to repository ports;
* application extraction.

### Suggested execution order

Second. This is the only intentionally broad cycle because the namespace move must be atomic to avoid either a compatibility layer or duplicate production implementations.

---

## Cycle 4.3.3 — Preserve historical data and operational buildability

### Goal

Ensure the package move does not accidentally alter compatibility data or make the supported workspace/Docker build depend on undeclared local state.

### Red

Retain and, where useful, sharpen the existing migration regression tests around the historical tag:

```text
tag:yaml.org,2002:python/object:bot.domain.user.StickfixUser
```

That string is data, not a live import path. The migration loader currently registers the historical tag without importing or instantiating the old class, which is exactly the behavior to retain.  Existing migration fixtures already exercise the old tag, so reuse them rather than creating a parallel fixture vocabulary.

Add metadata assurance that distinguishes these two conditions:

```text
no Python module imports bot.domain
historical migration data may still contain "bot.domain.user.StickfixUser"
```

Also add/extend package-build assurance so the root package cannot accidentally rely on `--all-packages` making an undeclared package available.

### Green

Preserve the compatibility strings byte-for-byte.

Update only the operational files required because `stickfix-domain` is now a real workspace dependency:

* `uv.lock`;
* the root `pyproject.toml`;
* Docker workspace-member copies if Phase 4.2 did not already make them generic;
* the existing CI quality path enough to exercise/build the new member.

This Docker detail should not be deferred to Phase 4.7. The current image copies only the root metadata and `bot/` before `uv sync`; once the root declares a workspace dependency, the corresponding workspace package must be present inside the build stage or the formerly supported Docker build can stop working.

Prefer extending the existing CI job with the domain build check instead of creating another job solely for this package.

### Refactor

Keep operational changes minimal. Full runtime namespace changes, Alembic relocation, final Docker restructuring, and repository-wide documentation reconciliation still belong to later Milestone 4 phases.

### Acceptance criteria

* historical YAML using the old object tag is still accepted;
* no replacement `stickfix_domain.*` historical tag is introduced;
* Docker still resolves the frozen workspace from a clean build context;
* CI exercises the new package;
* the root dependency edge is explicit rather than relying on `uv sync --all-packages`;
* application, PostgreSQL, migration, handler, and startup tests remain green.

### Non-goals

* changing the historical format;
* rewriting migration fixtures;
* runtime namespace extraction;
* broad Docker optimization;
* Alembic relocation.

### Suggested execution order

Third, immediately after the namespace cutover.

---

## Cycle 4.3.4 — Prove distribution independence and close the phase

### Goal

Verify not merely that the workspace source tree works, but that the **built distribution** has the promised package boundary.

### Red

Add or extend packaging-contract checks to inspect the built wheel rather than relying solely on:

```bash
uv run python -c "import stickfix_domain"
```

That command proves the workspace environment can import the package, but not that the wheel was assembled correctly.

The artifact checks should establish:

```text
given the built stickfix-domain wheel
when its contents and metadata are inspected
then it contains stickfix_domain and no legacy bot.domain package

given the built stickfix-domain wheel
when its METADATA is inspected
then it has no Requires-Dist runtime dependencies

given an environment containing only the built domain distribution and its build/runtime prerequisites
when its public API is imported
then the import succeeds
```

### Green

Resolve any setuptools package-discovery or metadata issues exposed by those checks without changing domain behavior.

Verify both the extracted package and the still-rooted runtime distribution:

```bash
uv lock --check
uv sync --all-packages --frozen

uv run ruff check .
uv run ruff format --check .
uv run pytest

uv build --package stickfix-domain
uv build --package stickfix-bot
```

Then perform an isolated smoke import from the built `stickfix-domain` wheel rather than only from the editable/shared workspace.

### Refactor

Remove temporary build artifacts from the working tree and keep artifact inspection reusable for Phases 4.4 and 4.5, where the same guarantees will be needed for application and Telegram packages.

Record Phase 4.3 completion in the active Milestone 4 traceability item. Avoid broad documentation restructuring here; final topology documentation remains part of the already-recorded Phase 4.7 work.

### Acceptance criteria

From a clean checkout:

```text
workspace lock is frozen and valid
all packages synchronize successfully
Ruff passes
the complete test suite passes
stickfix-domain builds
stickfix-bot still builds
the domain wheel imports in isolation
the domain wheel declares no runtime dependency
bot.domain does not exist
no production module imports bot.domain
historical YAML compatibility still uses and accepts the old tag
```

No Telegram command behavior, PostgreSQL schema/transaction behavior, migration semantics, logging semantics, startup semantics, or domain behavior changes.

### Non-goals

* independent package publishing;
* independent versioning;
* application or Telegram extraction;
* `uv_build`;
* PTB modernization;
* type-checker adoption;
* domain-model redesign.

### Suggested execution order

Last. This turns “the tests happen to pass in the workspace” into evidence that `stickfix-domain` is genuinely an independent distribution.

---

## Public interface contract

Keep the intended public surface deliberately small:

```python
from stickfix_domain import SF_PUBLIC, StickfixUser, Switch, UserId, UserModes
from stickfix_domain.services import StickerPackService
```

Submodule imports remain possible where technically necessary, particularly for tests that patch the module-level RNG, but production consumers should favor these exported entry points.

## Deferred design opportunity

There is one worthwhile architectural improvement I would **not** mix into this phase: `StickfixUser` currently accesses module-global `random` directly for both shuffle and random-tag behavior.  That is the main remaining effect inside an otherwise infrastructure-free domain. Injecting a narrow random-selection capability or controlled `Random` instance would improve deterministic testing and functional-core separation, but it changes the domain construction/API story and therefore deserves a separate behavior-characterized follow-up after the workspace extraction.

The key distinction in the revised phase is that **4.3 proves three independent things**: source-level architectural independence, metadata-level dependency correctness, and artifact-level build/install correctness. Your original plan covered the first two reasonably well, but the root dependency edge, the direct Telegram consumer, Docker workspace availability, and isolated-wheel verification were the main gaps.
