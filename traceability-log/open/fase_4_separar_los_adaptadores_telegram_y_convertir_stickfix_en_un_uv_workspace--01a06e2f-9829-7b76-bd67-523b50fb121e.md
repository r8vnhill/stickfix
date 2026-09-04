# Milestone 4 — Convert Stickfix into a modular `uv` workspace

## Goal

Transform Stickfix from the current `bot.*` package into four explicitly bounded Python distributions:

```text
stickfix-domain
stickfix-application
stickfix-telegram
stickfix-bot / stickfix_runtime
```

while preserving the current observable behavior of:

* Telegram commands and inline queries;
* PostgreSQL persistence and transaction semantics;
* historical YAML migration;
* logging;
* Alembic;
* Docker/runtime startup.

The milestone deliberately breaks the `bot.*` import namespace. No compatibility shims are introduced.

## Target dependency graph

```text
stickfix-bot
    ├──> stickfix-telegram
    ├──> stickfix-application
    └──> stickfix-domain

stickfix-telegram
    ├──> stickfix-application
    └──> stickfix-domain

stickfix-application
    └──> stickfix-domain

stickfix-domain
    └──> stdlib only
```

`stickfix_runtime.infrastructure` remains part of the root `stickfix-bot` distribution; it is not a fifth workspace member.

---

# Phase 4.1 — Stabilize the public Telegram adapter test seam [DONE]

## Goal

Make the existing Telegram behavior safe to move by ensuring handler tests exercise registered PTB callbacks rather than name-mangled implementation methods.

## Scope

Complete the already-started inline-handler seam work and apply the same contract to:

* `HelperHandler`;
* `UserHandler`;
* `StickerHandler`;
* `InlineHandler`.

Characterize through the registered callbacks:

* `/start`;
* `/help`;
* `/add`;
* `/get`;
* `/deleteFrom`;
* `/deleteMe`;
* `/setMode`;
* `/shuffle`;
* inline query;
* chosen inline result.

Preserve:

* registration order;
* response text;
* Markdown modes;
* greeting sticker;
* existing error handling;
* inline limit `49`;
* `cache_time=1`;
* `is_personal=True`;
* offsets and `next_offset`;
* current cache/fallback semantics.

Use DDT for repeated command/input matrices.

## Acceptance criteria

* no test invokes `_InlineHandler__...`, `_StickerHandler__...`, `_HelperHandler__...`, or `_UserHandler__...`;
* all Telegram handlers are exercised through their registered callbacks;
* handler tests cover transport mapping/rendering only;
* application tests remain authoritative for pagination, fallback, cache, and domain behavior;
* the open inline-handler seam traceability item can be closed;
* no production behavior changes.

## Non-goals

* workspace creation;
* namespace moves;
* Protocol refactoring beyond what is necessary for testability;
* pagination/order changes;
* PTB upgrade.

## Suggested execution order

First. This is the behavioral safety boundary for every subsequent package move.

---

# Phase 4.2 — Establish the `uv` workspace foundation

## Goal

Introduce a reproducible workspace structure without moving architectural layers yet.

## Scope

Update root packaging/tooling:

```text
pyproject.toml
uv.lock
Dockerfile
.github/workflows/ci.yml
```

Introduce:

```toml
[tool.uv.workspace]
members = ["packages/*"]
```

but initially without relocating production modules.

Clean dependency classification at the same time:

* development tooling → `[dependency-groups]`;
* Ruff and `uv` out of runtime dependencies;
* retain setuptools;
* retain Python `>=3.14,<4`;
* align the `uv` version used locally, CI, and Docker.

Introduce reusable architecture-test infrastructure capable of checking packages under arbitrary `src/` roots instead of assuming `bot.foo → bot/foo`.

Add metadata-contract helpers using `tomllib`, ready to validate workspace dependency edges in subsequent phases.

When touching the architecture checks, replace the current project-local `violates`/`violations` terminology with neutral names such as `matches_forbidden_prefix` and `nonconformances`, consistent with the project guidelines. 

## Acceptance criteria

* `uv sync --frozen` remains green;
* workspace configuration is valid;
* CI and Docker use the same `uv` release;
* QA tooling is absent from published runtime dependencies;
* architecture tests support both current `bot.*` and future `src/` package roots;
* no production namespace has moved.

## Non-goals

* extracting domain/application/Telegram;
* changing runtime entrypoints;
* major pytest/PTB upgrades;
* migration to `uv_build`.

## Suggested execution order

After Phase 4.1. This creates the infrastructure required by every package extraction.

---

# Phase 4.3 — Extract `stickfix-domain`

## Goal

Make the domain an independently buildable distribution with no dependency on any other Stickfix package.

## Scope

Create:

```text
packages/stickfix-domain/
├── pyproject.toml
└── src/
    └── stickfix_domain/
```

Move the current domain there and update all consumers.

Declare the package contract:

```text
stickfix-domain → {}
```

Enforce through AST and package metadata that the domain remains free of:

* Telegram;
* application;
* runtime/infrastructure;
* SQLAlchemy;
* psycopg;
* logging.

Remove `bot.domain` immediately once consumers are updated; do not introduce a compatibility shim.

## Acceptance criteria

* `uv build --package stickfix-domain` succeeds;
* `stickfix_domain` is importable after a clean workspace sync;
* `bot.domain` no longer exists;
* domain tests remain green;
* domain has no internal project dependencies;
* observable behavior is unchanged.

## Non-goals

* redesigning domain models;
* changing persistence ports;
* extracting application in the same phase.

## Suggested execution order

First package extraction.

---

# Phase 4.4 — Extract `stickfix-application`

## Goal

Make application an independently buildable package depending only on the domain package.

## Scope

Create:

```text
packages/stickfix-application/
├── pyproject.toml
└── src/
    └── stickfix_application/
```

Move:

* requests;
* results;
* application errors;
* ports;
* use cases.

Declare and enforce:

```text
stickfix-application → stickfix-domain
```

Generalize the existing application seam so importing `stickfix_application` does not load:

* Telegram;
* persistence infrastructure;
* SQLAlchemy;
* psycopg.

Update Telegram adapters and runtime composition to consume the new namespace.

Remove `bot.application` without a shim.

## Acceptance criteria

* `uv build --package stickfix-application` succeeds;
* application declares `stickfix-domain` directly as a workspace dependency;
* no Telegram or infrastructure import appears in application;
* DTO shape and use-case semantics remain unchanged;
* `bot.application` no longer exists.

## Non-goals

* redesigning DTOs;
* changing repository interfaces;
* transaction changes;
* Telegram extraction.

## Suggested execution order

After domain because it establishes the single allowed internal dependency.

---

# Phase 4.5 — Extract `stickfix-telegram`

## Goal

Turn the current Telegram layer into an independently buildable interface-adapter package.

## Scope

Create:

```text
packages/stickfix-telegram/
├── pyproject.toml
└── src/
    ├── stickfix_telegram/
    └── imghdr.py
```

Move and reorganize:

* handlers;
* command names;
* Telegram update/message mapping;
* replied-sticker extraction;
* Telegram result rendering;
* Telegram-specific error translation;
* unexpected adapter-error logging.

Do **not** preserve `bot/utils/messages.py` as one miscellaneous utility module. Split responsibilities around adapter cohesion.

Introduce narrow callable `Protocol`s for injected application collaborators so handlers depend on behavioral contracts rather than concrete use-case classes.

Enforce:

```text
stickfix-telegram
    → stickfix-application
    → stickfix-domain
```

and prohibit dependencies on:

```text
stickfix_runtime
sqlalchemy
psycopg
alembic
```

Keep the existing Python 3.14/PTB 13 `imghdr` compatibility behavior unchanged.

## Acceptance criteria

* `uv build --package stickfix-telegram` succeeds;
* every test from Phase 4.1 remains green through the new namespace;
* handlers depend on callable contracts rather than concrete repositories;
* Telegram does not import runtime/infrastructure;
* command registration and all visible responses are unchanged;
* legacy Telegram-only utilities under `bot.utils` are retired when no longer referenced.

## Non-goals

* PTB 13→modern async PTB;
* async conversion;
* changing the `imghdr` compatibility behavior;
* changing the Tornado workaround;
* changing inline semantics.

## Suggested execution order

After application. At this point the complete functional core is already physically separated.

---

# Phase 4.6 — Extract and package `stickfix_runtime`

## Goal

Convert the root distribution into the composition/operational shell for the three extracted packages.

## Scope

Move:

```text
bot/stickfix.py
    → src/stickfix_runtime/stickfix.py

bot/__main__.py
    → src/stickfix_runtime/__main__.py

bot/config.py
    → src/stickfix_runtime/config.py

bot/infrastructure/**
    → src/stickfix_runtime/infrastructure/**
```

Move `HELP.md` into package resources and access it through `importlib.resources`, eliminating the current working-directory-sensitive path.

Introduce the new public contracts:

```python
from stickfix_runtime.stickfix import Stickfix
```

and:

```bash
python -m stickfix_runtime
```

Preserve the current composition architecture: runtime constructs infrastructure adapters and use cases, then injects the use cases into Telegram adapters.

Keep migration infrastructure inaccessible from the normal bot composition path.

## Acceptance criteria

* `uv build --package stickfix-bot` succeeds;
* `Stickfix` imports through the new public namespace;
* `python -m stickfix_runtime` starts through the existing configuration path;
* packaged `HELP.md` is readable from an installed wheel;
* PostgreSQL and logging behavior remain unchanged;
* normal runtime imports no migration modules.

## Non-goals

* changing the composition architecture;
* dependency-injection framework;
* PostgreSQL redesign;
* migration redesign.

## Suggested execution order

After all three inner packages exist, making runtime the final composition shell.

---

# Phase 4.7 — Integrate operational tooling and retire `bot.*`

## Goal

Make the new workspace topology the only supported topology and prove it works from a clean checkout and packaged artifacts.

## Scope

Update all operational integrations:

```text
alembic/env.py
Dockerfile
.github/workflows/ci.yml
README.md
AGENTS.md
CONTRIBUTING.md
ARCHITECTURE-PORTS-ANALYSIS.md
Changelog.md
traceability-log/
```

Update migration scripts and tests to the new runtime namespace.

Make architecture rules merge-gating at two independent levels.

### Python imports

```text
stickfix_domain
    → no Stickfix package

stickfix_application
    → stickfix_domain

stickfix_telegram
    → stickfix_application + stickfix_domain

stickfix_runtime
    → all three
```

### Package metadata

```text
stickfix-domain      -> {}
stickfix-application -> {stickfix-domain}
stickfix-telegram    -> {stickfix-domain, stickfix-application}
stickfix-bot         -> {stickfix-domain, stickfix-application, stickfix-telegram}
```

Finally remove the remaining `bot/` tree.

The `bot.*` strings embedded in historical YAML compatibility data are allowed; the architectural rule must inspect imports, not perform a raw textual search.

## Acceptance criteria

From a clean checkout:

```bash
uv sync --all-packages --frozen

uv run ruff check .
uv run ruff format --check .
uv run pytest

uv run alembic upgrade head
uv run alembic check
uv run pytest -m integration

uv build --package stickfix-domain
uv build --package stickfix-application
uv build --package stickfix-telegram
uv build --package stickfix-bot
```

Additionally:

* Docker builds and starts with `python -m stickfix_runtime`;
* Alembic uses the new persistence-model namespace;
* migration still accepts historical YAML;
* no Python module imports `bot.*`;
* `bot/` no longer exists;
* all four `pyproject.toml` files conform to the dependency graph;
* documentation describes PostgreSQL as runtime persistence and YAML as migration-only;
* the deliberate public import break is recorded in traceability/changelog;
* no Telegram, PostgreSQL, logging, or migration semantics changed.

## Non-goals

* publishing internal packages independently;
* independent package versioning;
* PTB modernization;
* new type checker;
* Docker reproducibility redesign beyond the namespace/workspace changes.

---

## Suggested milestone execution order

```text
4.1 Telegram test seam
        ↓
4.2 Workspace foundation
        ↓
4.3 Domain package
        ↓
4.4 Application package
        ↓
4.5 Telegram package
        ↓
4.6 Runtime package
        ↓
4.7 Operational integration + bot.* removal
```

This boundary is much healthier. In particular, **each of 4.3–4.6 leaves `main` in a coherent, buildable intermediate state** and has one primary architectural outcome. Then each individual phase can be expanded later into perhaps 2–4 short Red/Green/Refactor cycles rather than carrying the entire repository migration at once.
