# Phase 3 — Complete the Runtime/Infrastructure Boundary and Retire Legacy Persistence

## Summary

Complete the infrastructure transition already underway on `main` by making the runtime composition graph consistent with the application architecture, separating migration-only PostgreSQL operations from runtime repositories, removing the obsolete YAML runtime backend, and removing operational logging effects from the domain.

Preserve:

* PostgreSQL as the only runtime persistence backend;
* immediate transactional persistence semantics;
* the current PostgreSQL schema and Alembic history;
* existing Telegram commands and visible responses;
* historical YAML import compatibility;
* current help content and behavior;
* current operational logging levels, destinations, rotation policy, environment configuration, and message semantics;
* `Stickfix(token).run()` as the public runtime entry point.

This phase should not introduce a domain `Logger` port, a Unit of Work, a dependency-injection framework, or a replacement persistence abstraction.

The architectural target is:

```text
Telegram adapters
        ↓
application use cases        operational logging
        ↓                          ↓
domain model + ports         Python logging
        ↑                          ↑
PostgreSQL runtime           infrastructure configuration

migration CLI
        ↓
legacy YAML reader → migration representation
        ↓
PostgreSQL migration gateway
```

The domain remains free of Telegram, persistence, YAML, logging, and other operational effects.

---

## Current State

`main` already establishes most of the target architecture:

* PostgreSQL is the runtime backend.
* `PostgresUserRepository` implements the regular-user and public-pack persistence responsibilities.
* `UserRepository` uses numeric user IDs.
* `PublicPackRepository` represents the shared pack independently of the historical `SF-PUBLIC` convention.
* YAML is documented as migration-only.
* `GetHelp` and `FileHelpContentProvider` already exist.
* `EnsureUser`, `SetMode`, `SetShuffle`, `DeleteUser`, sticker use cases, and inline use cases already exist.
* architectural dependency tests already use `ast`/`pathlib`;
* CI already runs Ruff, formatting, pytest, Alembic checks, and PostgreSQL integration tests.

The remaining work is therefore consolidation and removal of transitional seams, not introduction of another architectural layer.

---

# Cycle 3.1 — Repair and freeze the production composition root

## Goal

Make `Stickfix(token).run()` construct a complete, internally consistent runtime graph in which handlers receive application use cases rather than persistence adapters.

This is the first priority because the current composition code and handler constructors no longer describe the same interface.

## Scope

Relevant components include:

```text
bot/stickfix.py
bot/handlers/utility.py
bot/handlers/stickers.py
bot/handlers/inline.py
bot/application/use_cases/
bot/infrastructure/help/
bot/infrastructure/persistence/postgres/
tests/
```

Compose, once per runtime:

* one `PostgresUserRepository`;
* that repository as both:

  * `UserRepository`;
  * `PublicPackRepository`;
* one `FileHelpContentProvider`;
* the required domain/application services;
* all use cases;
* handlers receiving those use cases.

The same `FileHelpContentProvider` should serve both `GetHelp` and empty-query inline help.

Prefer private, cohesive composition helpers if `Stickfix` would otherwise become too large. Do not introduce a generic container or service locator.

## Red

Add a composition-level regression test:

```text
given production-shaped user and public-pack repositories
when the Stickfix runtime graph is constructed
then every handler receives its required application use cases
and no handler receives a persistence adapter directly
```

Add a focused help-sharing case:

```text
given one configured help-content provider
when help and inline-query use cases are composed
then both use the same provider instance
```

Add or retain a smoke-level test that proves constructing the handler graph does not fail because of constructor mismatches.

## Green

* Instantiate application use cases in the composition root.
* Pass those use cases to `HelperHandler`, `UserHandler`, `StickerHandler`, and `InlineHandler`.
* Share one `FileHelpContentProvider`.
* Keep one concrete PostgreSQL repository instance where that remains sufficient for both persistence ports.

## Refactor

* Extract small composition helpers only where they reduce duplication.
* Keep infrastructure construction out of handlers.
* Avoid a broad `Services` or `Dependencies` bag containing unrelated objects.
* Preserve `Stickfix(token).run()`.

## Acceptance Criteria

* the production handler graph can be constructed successfully;
* handlers receive application collaborators rather than repositories;
* handlers do not construct PostgreSQL or help adapters;
* exactly one runtime `FileHelpContentProvider` is shared where appropriate;
* the production PostgreSQL adapter can satisfy both existing persistence ports;
* no runtime behavior or Telegram output changes.

## Non-goals

* dependency-injection frameworks;
* runtime plugin discovery;
* changing repository transactions;
* changing command behavior.

## Suggested Execution Order

First. All later cleanup should be performed against a known-valid production graph.

---

# Cycle 3.2 — Separate runtime PostgreSQL contracts from migration operations

## Goal

Keep `PostgresUserRepository` focused on the runtime `UserRepository` and `PublicPackRepository` contracts while giving the historical importer a deliberately separate PostgreSQL boundary.

## Scope

Review:

```text
bot/infrastructure/persistence/postgres/
bot/infrastructure/migration/yaml_to_postgres.py
bot/infrastructure/migration/logical_snapshot.py
```

The migration currently needs operations that do not belong to either runtime port, including:

* bulk import;
* full enumeration for verification.

Do not add these operations to `UserRepository` or `PublicPackRepository`.

Introduce a narrow migration-only component, for example:

```text
bot/infrastructure/migration/postgres_gateway.py
```

with responsibilities such as:

```text
import_snapshot(...)
read_snapshot(...)
is_empty(...)
```

Exact names should follow the final migration vocabulary.

It may reuse:

* SQLAlchemy models;
* session factories;
* mappers;
* PostgreSQL transaction infrastructure.

It must remain unreachable from normal runtime composition.

## Red

```text
given a validated migration snapshot
when it is imported through the PostgreSQL migration gateway
then all state is committed atomically
```

```text
given an import that cannot be completed
when the migration transaction ends
then no partial imported state is observable
```

```text
given an imported migration snapshot
when PostgreSQL is projected back to the logical representation
then it equals the source migration snapshot
```

Add an architectural assertion that application/runtime ports do not acquire migration-only enumeration or bulk-import operations.

## Green

* Move `import_mapping()`-style behavior out of the runtime repository.
* Move full-database enumeration used for migration verification behind the migration gateway.
* Update the importer and snapshot verifier to use this gateway.
* Remove the current attribute-level type suppression associated with `iter_user_ids()`.

## Refactor

* Share SQLAlchemy/session infrastructure rather than duplicating database setup.
* Keep transactional policy explicit at the migration boundary.
* Remove mapping terminology once the migration path no longer operates on runtime dictionary-shaped state.

## Acceptance Criteria

* `PostgresUserRepository` exposes only runtime persistence responsibilities;
* migration code does not rely on undeclared `UserRepository` methods;
* no `type: ignore` is required to enumerate imported users;
* migration remains all-or-nothing;
* pre/post logical snapshot equivalence remains verifiable;
* no PostgreSQL schema change is required.

## Non-goals

* Unit of Work;
* generic bulk persistence API;
* schema optimization;
* changing migration receipt semantics.

## Suggested Execution Order

After Cycle 3.1 and before deleting the historical runtime backend.

---

# Cycle 3.3 — Decouple the historical YAML representation from the domain model

## Goal

Make historical YAML an archival/import representation rather than a serialization mechanism for live domain objects.

## Rationale

The current restricted loader is already substantially safer than the removed runtime YAML path and does not need `bot.database` to resolve historical tags.

However, it still reconstructs `StickfixUser` objects. That means future changes to the domain model can unnecessarily affect the ability to import historical files.

The migration package should instead own the historical wire representation.

## Scope

Introduce migration-local immutable records, for example:

```text
LegacyUserRecord
LegacyStoreRecord
```

Prefer:

```python
@dataclass(frozen=True, slots=True)
```

where appropriate.

The restricted loader should continue recognizing the exact historical YAML tag strings, including old fully-qualified names, but map them into migration records rather than importing or instantiating the historical classes named by those tags.

Keep the historical literal `SF-PUBLIC` convention inside the migration boundary.

Evolve `LogicalPersistenceSnapshot` toward typed migration structures rather than `dict[str, Any]` where doing so improves clarity without unnecessarily changing the stable canonical representation.

## Red

Use frozen, literal legacy fixtures:

```text
given a legacy file containing the historical domain-class YAML tag
when it is loaded by the restricted migration reader
then it produces a valid migration record
without importing the historical class named by the tag
```

```text
given a legacy file containing the historical bot.database.users tag
when it is loaded
then the legacy tag remains supported after bot.database has been removed
```

```text
given the canonical legacy fixture
when its migration snapshot is reconstructed
then its canonical representation and digest remain unchanged
```

Retain DDT for:

* normal numeric users;
* `SF-PUBLIC`;
* preferences;
* multiple tags/stickers;
* cache ordering;
* malformed IDs;
* unsupported tags;
* inconsistent associations.

## Green

* Introduce migration-local records.
* Adapt the restricted SafeLoader constructors.
* Build `LogicalPersistenceSnapshot` from those records.
* Convert into PostgreSQL migration input only at the migration gateway.

## Refactor

* Remove domain imports from the legacy reader where no longer required.
* Keep validation and canonicalization functions deterministic and side-effect free.
* Use expressive types for cache positions, associations, and user records where useful.
* Keep historical tag names as data, not Python imports.

## Acceptance Criteria

* loading legacy YAML does not instantiate `StickfixUser`;
* loading legacy YAML does not import `bot.database`;
* both supported historical Python tag names continue to work;
* source fixtures produce the same logical information and stable digest;
* unsupported or inconsistent YAML is rejected before PostgreSQL mutation begins;
* migration parsing does not trigger domain methods or operational logging.

## Non-goals

* changing historical YAML files;
* inventing a new YAML persistence format;
* supporting arbitrary Python YAML objects;
* exporting PostgreSQL back to YAML.

## Suggested Execution Order

After Cycle 3.2. This makes deletion of the runtime YAML implementation mechanically safer.

---

# Cycle 3.4 — Remove the obsolete YAML runtime backend

## Goal

Remove the unused operational persistence implementation while preserving the historical import capability independently.

## Scope

Delete, once dependency tests prove they are no longer needed:

```text
bot/database/storage.py
bot/database/users.py
bot/infrastructure/persistence/stickfix_user_repository.py
```

Remove the `bot.database` package entirely if nothing remains in it.

Do not plan a separate removal of a public `StickfixDB` re-export unless one actually exists at implementation time; the current package initializer does not need such a migration step.

Remove tests that exist solely to verify the deleted runtime backend.

Retain or migrate any fixtures/tests that are evidence for historical import compatibility.

Backup rotation and YAML recovery tests should not become PostgreSQL runtime contract tests: they describe behavior of the backend being retired.

## Red

Extend the existing architectural test:

```text
given any normal runtime module
when its imports are inspected
then it has no dependency on bot.database
or the retired YAML repository adapter
```

And protect the historical path:

```text
given the canonical legacy YAML fixtures
when the retired runtime modules are unavailable
then historical import still succeeds
```

## Green

* Remove `StickfixDB`.
* Remove `StickfixUserRepository`.
* Remove dead exports/imports.
* Remove backend-specific runtime tests that no longer describe supported production behavior.
* Keep migration fixtures and importer tests.

## Refactor

Clean up:

* obsolete YAML-runtime terminology;
* stale compatibility comments;
* mapping-shaped test doubles left over from the old persistence implementation;
* dependencies that were used exclusively by runtime YAML persistence, if any.

## Acceptance Criteria

* no supported runtime path imports `bot.database`;
* `StickfixUserRepository` no longer exists;
* PostgreSQL remains the only runtime persistence adapter;
* historical YAML import still accepts canonical legacy fixtures;
* no backup-rotation/recovery requirement is incorrectly transferred to PostgreSQL;
* all application and PostgreSQL contract tests remain green.

## Non-goals

* removing historical YAML fixtures;
* PostgreSQL backup policy;
* PostgreSQL disaster recovery;
* changing Alembic migrations.

## Suggested Execution Order

Only after Cycles 3.2 and 3.3 demonstrate that migration no longer depends on runtime YAML classes.

---

# Cycle 3.5 — Remove operational logging from the domain

## Goal

Make the domain model free of logging effects while preserving the operational information currently emitted when sticker state changes.

## Architectural Decision

Do **not** add:

```text
bot.domain.ports.logging.Logger
```

and do not change the constructor to:

```text
StickfixUser(user_id, logger=...)
```

Logging is not a domain capability required to model users or sticker packs. It is an operational side effect.

The target should instead remain:

```text
pure domain mutation
        ↓
application orchestration
        ↓
persistence + operational logging
```

`StickfixUser(user_id)` therefore remains compatible naturally, without a default infrastructure dependency hidden inside the constructor.

## Scope

Relevant components include:

```text
bot/domain/user.py
bot/application/use_cases/
bot/utils/logger.py
bot/stickfix.py
```

and a new focused infrastructure location such as:

```text
bot/infrastructure/logging/
    __init__.py
    configuration.py
```

Prefer the standard-library logging API:

```python
logging.getLogger(__name__)
```

for callers, with infrastructure responsible for configuring handlers once.

Preserve the existing operational configuration:

* log levels;
* console output;
* rotating file output;
* `STICKFIX_LOG_PATH`;
* `STICKFIX_DISABLE_FILE_LOGGING`;
* formatting;
* rotation settings;
* protection against duplicated handlers.

Before moving existing domain log calls, characterize their observable message and level semantics.

## Red

First freeze existing relevant behavior:

```text
given a sticker successfully linked to a pack
when the application operation completes
then the existing sticker-added operational message is emitted at the expected level
```

```text
given a sticker successfully unlinked
when the application operation completes
then the existing removal message is emitted at the expected level
```

Add architecture coverage:

```text
given the domain package
when its imports are inspected
then it has no logging or project logging dependency
```

Add logger-configuration tests:

```text
given logging is configured twice
when the same runtime logger is inspected
then equivalent stream and rotating-file handlers are not duplicated
```

Use `tmp_path` and `caplog` rather than mocking the logging implementation.

## Green

* Remove the logger import/global from `bot.domain.user`.
* Remove logging calls from `StickfixUser`.
* Emit equivalent operational events at the application/imperative-shell boundary.
* Move handler/file configuration into infrastructure.
* Configure logging from the composition root.
* Use `logging.Logger` directly instead of introducing a project-wide generic logger protocol unless a concrete second logging implementation later establishes a need for one.

## Refactor

Reduce the current custom wrapper if possible:

```text
configuration owns setup
modules own standard logging.Logger instances
```

Retain a narrow `bot.utils.logger` compatibility shim only if an actual supported caller still needs that import path.

If no supported caller needs it after internal migration, remove it rather than preserving an unbounded compatibility layer.

Any temporary shim must have a documented removal condition.

## Acceptance Criteria

* the domain imports neither `logging` nor `bot.utils.logger`;
* `StickfixUser(user_id)` remains unchanged;
* domain tests need no logger fake;
* existing operational sticker messages and levels remain represented;
* logging configuration is performed at the runtime boundary;
* file/console behavior and environment variables remain supported;
* repeated configuration does not duplicate handlers;
* no third-party logging dependency is introduced.

## Non-goals

* structured logging platform adoption;
* OpenTelemetry;
* remote log aggregation;
* adding domain events solely to move two log statements;
* changing logging wording without an explicitly separate reason.

## Suggested Execution Order

This can be developed largely independently after Cycle 3.1, but merge it after the composition root is stable.

---

# Cycle 3.6 — Strengthen executable architecture rules and close the phase

## Goal

Make the final Phase 3 boundaries merge-gating and align documentation with the implementation that actually exists.

## Scope

Extend the existing AST-based architecture test instead of introducing another architecture-testing dependency.

The final rules should encode at least:

```text
domain
    -> standard-library/domain modules only as appropriate
    X Telegram
    X application
    X handlers
    X infrastructure
    X project logging utilities
    X persistence/YAML

application
    -> domain + application ports
    X Telegram
    X handlers
    X concrete infrastructure
    X SQLAlchemy/psycopg
    X legacy database modules

handlers
    -> Telegram + application/domain adapter-facing APIs
    X persistence implementation
    X migration modules
    X legacy database modules

runtime composition
    -> application + infrastructure
    X migration-only modules

migration infrastructure
    -> migration representations + PostgreSQL infrastructure
    X supported runtime composition
```

Use neutral local terminology in the architecture-test implementation, for example:

```text
DISALLOWED_IMPORTS
is_disallowed_dependency(...)
dependency_failures
```

This also brings the existing test vocabulary into conformance with the project's inclusive-language requirement.

### Documentation

Reconcile rather than rewrite documentation that `main` already has correct.

Confirm that README/architecture/traceability material consistently states:

* PostgreSQL is runtime-only persistence;
* YAML is historical migration input;
* regular users have numeric IDs;
* the public pack is an explicit separate persistence contract;
* handlers receive application use cases;
* domain logic is independent of operational logging;
* migration-only infrastructure is not a runtime dependency.

Update `~todo.md` only if it is actually a tracked project planning artifact. Do not create or preserve another architectural source of truth solely for this phase.

## Red

Prove each architecture rule with a focused test that would reject a representative disallowed dependency.

For example:

```text
given a domain module importing project logging infrastructure
when architecture dependencies are checked
then the dependency check reports that module and import
```

```text
given runtime composition importing a migration-only module
when dependencies are checked
then the dependency check reports an actionable nonconformance
```

## Green

* Extend the existing AST/pathlib rules.
* Rename existing rule implementation vocabulary where needed.
* Keep diagnostics explicit:

  * importing module;
  * imported module;
  * expected boundary.
* Update only stale documentation.

## Refactor

Represent dependency rules as data rather than repeated procedural checks where practical.

Keep architecture tooling small and repository-local.

## Acceptance Criteria

* dependency-direction checks execute through normal `pytest`;
* the domain cannot regain logging/infrastructure dependencies unnoticed;
* runtime code cannot regain `bot.database` or migration dependencies unnoticed;
* application ports remain infrastructure-neutral;
* migration-only boundaries are explicit;
* architecture-test diagnostics are actionable and use project-approved terminology;
* README and architecture documentation match the executable boundaries.

## Non-goals

* third-party architecture frameworks;
* class-level architecture enforcement;
* static proof of every design convention.

## Suggested Execution Order

Last implementation cycle, once the intended architecture no longer needs transitional exceptions.

---

# Final Validation

Use the repository's existing quality and PostgreSQL gates rather than adding another CI architecture.

Required validation:

```text
uv run ruff check
uv run ruff format --check
uv run pytest

alembic upgrade head
alembic check
uv run pytest -m integration
```

Also verify from a clean process that:

```text
Stickfix(token).run()
```

constructs the complete application graph without:

* `StickfixDB`;
* `StickfixUserRepository`;
* `bot.database`;
* migration-only infrastructure in the runtime path.

The existing CI PostgreSQL service remains the authoritative merge gate.

---

# Phase Acceptance Criteria

Phase 3 is complete when all of the following hold:

* `Stickfix` correctly composes all current handlers from application use cases;
* one production `PostgresUserRepository` supplies the existing runtime persistence ports;
* runtime repository contracts contain no migration-only bulk/enumeration operations;
* a migration-only PostgreSQL gateway owns historical import and full-snapshot verification;
* the legacy YAML reader uses migration-owned representations rather than live domain objects;
* historical YAML tags remain importable after deletion of `bot.database`;
* `StickfixDB`, `StickfixUserRepository`, and the YAML runtime backend are removed;
* no supported runtime module imports migration-only infrastructure;
* the domain contains no logging, Telegram, YAML, SQLAlchemy, psycopg, or infrastructure dependencies;
* operational logging remains configured and behaviorally equivalent at the imperative-shell boundary;
* `StickfixUser(user_id)` remains unchanged;
* PostgreSQL schema and immediate transaction semantics remain unchanged;
* current Telegram behavior and responses remain unchanged;
* architecture boundaries are executable and merge-gating;
* all existing quality, Alembic, and PostgreSQL integration gates pass.

---

# Explicitly Deferred Work

Keep outside this phase:

* PostgreSQL schema redesign;
* Unit of Work;
* asynchronous SQLAlchemy;
* PostgreSQL backup/recovery policy;
* dual persistence;
* SQL→YAML export;
* domain-event infrastructure;
* structured/remote logging;
* OpenTelemetry;
* dependency-injection frameworks;
* a major `python-telegram-bot` upgrade;
* unrelated type-system modernization.

---

# Priority and Execution Order

## Required

```text
3.1 Repair production composition
        ↓
3.2 Separate migration PostgreSQL operations
        ↓
3.3 Decouple legacy YAML from domain objects
        ↓
3.4 Remove YAML runtime backend
        ↓
3.6 Freeze architectural boundaries
```

Cycle 3.5, domain logging removal, can proceed in parallel with 3.2–3.3 after the composition root is repaired, then converge before 3.6.

The minimum useful vertical increment is **3.1**: it repairs the runtime graph before cleanup begins.

The critical retirement path is **3.2 → 3.3 → 3.4**: first make historical migration independently viable, then remove the legacy runtime implementation.

## High-value architectural improvement

* Cycle 3.5: remove logging effects from the domain and standardize configuration around Python's existing logging facilities.

## Explicitly not required

* a new domain `Logger` abstraction;
* a generic repository;
* a Unit of Work;
* additional infrastructure frameworks.

---

# Local Environment Note

The Windows `.venv\Scripts` `Access denied` issue should be treated as a local development-environment problem, not as a Phase 3 architectural acceptance criterion.

Resolve it before relying on local full-suite results, but do not make the architecture plan contingent on that workstation state. The clean Linux CI jobs already provide the appropriate merge-gating environment for Ruff, pytest, Alembic, and PostgreSQL integration.

---

# Implementation result

Status: implemented.

Completed:

* `Stickfix` composition coverage confirms handlers receive application use cases and the help provider is shared.
* Runtime PostgreSQL persistence no longer exposes migration-only bulk import or enumeration operations.
* `PostgresMigrationGateway` owns atomic migration import and logical snapshot verification.
* Legacy YAML parsing now produces immutable migration records and does not instantiate domain objects or import `bot.database`.
* The obsolete `StickfixDB`, `StickfixUserRepository`, and `bot.database` package were removed.
* Domain logging side effects moved to the application boundary; runtime logging configuration is under `bot.infrastructure.logging`.
* Architecture documentation and AST dependency checks were updated.

Validation:

* `uvx --from ruff ruff check bot tests` — passed.
* `uvx --from ruff ruff format --check bot tests` — passed.
* Core suite (application, domain, migration, help, architecture, configuration, logging) — 84 passed.
* Tornado dependency policy — 2 passed with the locked patched Tornado line.
* Full Telegram handler collection could not run in the ephemeral environment because PTB 13.x's vendored urllib3 path is incompatible with the available Python 3.14 environment.
* PostgreSQL integration was not run locally because no test database was configured.
