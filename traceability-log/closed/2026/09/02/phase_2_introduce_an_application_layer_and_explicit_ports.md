# Phase 2 Closure — Make the Application Boundary Explicit and Merge-Gating

## Summary

Finish Phase 2 by removing the remaining compatibility seams between the current application architecture and the former YAML/mapping-based design.

The application layer and explicit ports already exist. The remaining work is therefore not to introduce another architectural layer, but to make the current architecture internally consistent:

* make `UserRepository` and `PublicPackRepository` explicit dependencies instead of recovering the public pack through legacy duck typing;
* remove transport-only or semantically misleading fields from application request DTOs;
* finish moving infrastructure composition out of Telegram handlers;
* replace legacy mapping-shaped test doubles with fakes that conform to the current ports;
* add focused coverage for the use cases added during the PostgreSQL migration;
* make dependency-direction rules executable in CI.

This work is behavior-preserving. The compatibility baseline is the **current `main` behavior**, including PostgreSQL's immediate transactional persistence. Historical YAML persistence timing is no longer part of Phase 2 compatibility.

The only intentionally deferred Telegram-facing flow is `/help` if moving it behind the existing `HelpContentProvider` would materially enlarge the change. Prefer completing it in this phase if it remains a small vertical slice.

---

## Current State

Already implemented on `main`:

* `bot.application` with:

  * request DTOs;
  * result DTOs;
  * application errors;
  * `Protocol`-based ports;
  * use cases.
* numeric `UserId`;
* separate `UserRepository` and `PublicPackRepository` contracts;
* PostgreSQL as the runtime persistence backend;
* immediate transactions for runtime mutations;
* `StickerPackService` as a Telegram-free domain service;
* use cases for:

  * `/start`;
  * `/add`;
  * `/get`;
  * `/deleteFrom`;
  * `/setMode`;
  * `/shuffle`;
  * `/deleteMe`;
  * inline query resolution;
  * inline cache clearing.
* Telegram handlers already delegate most behavioral decisions to those use cases;
* `FileHelpContentProvider` exists;
* CI already runs:

  * Ruff;
  * formatting checks;
  * the full test suite;
  * PostgreSQL integration tests;
  * Alembic upgrade/check.

Remaining architectural inconsistencies:

* `_LegacyPublicPackRepository` still reconstructs the public-pack contract dynamically from legacy mapping-shaped objects;
* application helpers still know the literal legacy identity `"SF-PUBLIC"`;
* some application tests still model `StickfixDB`, string user IDs, and mapping APIs;
* `AddStickerCommand` and `DeleteStickerCommand` carry `chat_id` and `chat_type` even though their use cases do not consume them;
* `GetStickersQuery` carries raw `chat_id` and `chat_type`, although only the private/non-private interaction distinction matters;
* `GetStickers` uses `UserModes.PRIVATE` to represent a private Telegram chat, conflating storage mode with interaction context;
* `ClearInlineCacheCommand.query_text` is currently unused;
* `InlineHandler` constructs `FileHelpContentProvider` and domain/application collaborators itself rather than receiving fully composed dependencies;
* dedicated application tests are still missing for some recently introduced use cases;
* dependency-direction guarantees are documented but not yet enforced structurally.

---

# Cycle 2.1 — Remove the legacy public-pack compatibility bridge

## Goal

Make regular-user persistence and public-pack persistence explicit application dependencies, with no mapping introspection or synthetic public-user identity inside the application layer.

## Scope

Relevant components:

* `bot/application/use_cases/_repositories.py`;
* sticker and inline use cases;
* `bot/application/ports/`;
* `bot/stickfix.py`;
* handler composition where repositories are forwarded;
* application test fakes.

Change the sticker/public-pack use cases so that `PublicPackRepository` is a required dependency wherever public-pack behavior is possible:

* `AddSticker`;
* `GetStickers`;
* `DeleteSticker`;
* `ResolveInlineQuery`;
* `ClearInlineCache`.

Remove:

* `_LegacyPublicPackRepository`;
* `public_repository(...)`;
* `getattr`-based repository discovery;
* mapping fallbacks;
* direct recognition of `"SF-PUBLIC"` from application code.

Production may continue using one `PostgresUserRepository` object that implements both ports. The important distinction is contractual, not necessarily one class or database session per port.

For tests, introduce small explicit fakes implementing the two ports instead of teaching application code to accommodate historical test doubles.

## Red

Add the smallest failing tests describing the intended contract.

```text
given separate user and public-pack repositories
when a sticker is added in public mode
then the public-pack repository is mutated
and no synthetic regular-user id is used
```

```text
given a private user and a public pack
when the effective pack is resolved
then regular-user access goes through UserRepository
and public-pack access goes through PublicPackRepository
```

```text
given an application use case that can access the public pack
when it is constructed
then an explicit PublicPackRepository is required
```

Reuse the same cases for sticker and inline behavior through DDT where practical.

## Green

* Require `PublicPackRepository` explicitly in the affected constructors.
* Pass the same PostgreSQL adapter as both ports in production composition.
* Replace legacy mapping-shaped application fakes with explicit port fakes.
* Remove the compatibility bridge.

Do not split `PostgresUserRepository` into two concrete classes merely because there are two ports; the current implementation can satisfy both coherently.

## Refactor

* Keep `_repositories.py` only for genuine application-level operations such as:

  * effective-user resolution;
  * effective-pack persistence;
  * common not-found semantics.
* Rename helpers so they describe application semantics rather than persistence compatibility.
* Remove casts and `type: ignore` annotations made unnecessary by the explicit ports.

## Acceptance Criteria

* no `_LegacyPublicPackRepository` exists;
* no application code uses `getattr` to discover persistence capabilities;
* no application code depends on mapping operations such as `values()`, `__getitem__`, or `__setitem__`;
* `"SF-PUBLIC"` is absent from application-layer persistence logic;
* `UserRepository` remains restricted to numeric regular users;
* `PublicPackRepository` is the only application contract for the shared pack;
* production may use the same PostgreSQL adapter instance for both ports;
* existing visible sticker and inline behavior remains unchanged.

## Non-goals

* splitting PostgreSQL into two physical repositories;
* introducing a Unit of Work;
* changing database transactions;
* changing the PostgreSQL schema;
* modifying the YAML importer.

## Suggested Execution Order

Do this first. Most remaining cleanup becomes simpler once tests and use cases stop depending on the compatibility bridge.

---

# Cycle 2.2 — Tighten application request semantics

## Goal

Make request DTOs express only application concepts actually consumed by use cases, without Telegram-shaped data or conflated enums.

## Scope

Review:

* `bot/application/requests.py`;
* `AddSticker`;
* `GetStickers`;
* `DeleteSticker`;
* `ClearInlineCache`;
* `StickerHandler`;
* inline handler request construction;
* corresponding tests.

### Sticker mutation requests

Remove unused:

```text
chat_id
chat_type
```

from:

* `AddStickerCommand`;
* `DeleteStickerCommand`.

These use cases currently need the actor, sticker, emoji/tags, and repository state—not Telegram chat identity.

### `/get` interaction context

Replace raw:

```text
chat_id: str
chat_type: str
```

with one application-level concept describing the semantic distinction the use case needs.

Prefer, for example:

```text
InteractionScope.PRIVATE
InteractionScope.NON_PRIVATE
```

or an equally precise small enum.

The Telegram adapter maps Telegram chat types to this application concept.

Do **not** reuse `UserModes.PRIVATE` for interaction context. `UserModes` describes which sticker pack a user selects; it does not describe where a command was invoked.

### Inline cache request

Remove `ClearInlineCacheCommand.query_text` if no current behavior depends on it.

The chosen-result query may remain available to the Telegram adapter for logging, but it should not cross the application boundary when the use case only needs the cache owner.

## Red

```text
given an /add command received in any Telegram chat type
when the handler builds AddStickerCommand
then the application request contains only sticker-operation data
```

```text
given a private Telegram chat
when the handler adapts /get
then the use case receives InteractionScope.PRIVATE
```

```text
given any non-private Telegram chat type
when /get is adapted
then the application receives a non-private interaction scope
and preserves the existing rejection behavior
```

Use DDT for Telegram private/group/supergroup/channel inputs if those distinctions are represented in existing tests.

```text
given a chosen inline result
when cache clearing is requested
then only the effective user identity is required by ClearInlineCache
```

## Green

Implement the smallest DTO and adapter changes necessary.

Keep raw strings for `/setMode` and `/shuffle` inputs where the use case intentionally owns validation. Moving those validations back into the Telegram handler would weaken the application seam.

## Refactor

* keep transport-to-application conversion in focused handler helpers;
* avoid introducing a general Telegram DTO mapper;
* keep bounded application concepts typed;
* remove request fields that are carried through layers without being consumed.

## Acceptance Criteria

* application request objects contain no unused Telegram chat identifiers;
* pack mode and interaction context have distinct types and names;
* `GetStickers` no longer compares Telegram interaction state against `UserModes`;
* `ClearInlineCacheCommand` contains no unused query payload;
* handlers preserve exactly the existing Telegram replies and calls.

## Non-goals

* redesigning every application DTO;
* changing command syntax;
* changing Telegram chat support;
* introducing validation libraries.

## Suggested Execution Order

Perform after Cycle 2.1 so the DTO cleanup is tested against the final repository contracts.

---

# Cycle 2.3 — Finish the imperative-shell composition boundary

## Goal

Make `Stickfix` the actual composition root and keep Telegram handlers focused on Telegram input/output translation.

## Scope

At minimum:

* `bot/stickfix.py`;
* `bot/handlers/inline.py`;
* `bot/infrastructure/help/file_help_content_provider.py`.

Move `FileHelpContentProvider` construction out of `InlineHandler`.

Prefer constructing shared infrastructure and application collaborators in `Stickfix`:

```text
PostgresUserRepository
FileHelpContentProvider
StickerPackService
        ↓
application use cases
        ↓
Telegram handlers
```

Handlers should not import `bot.infrastructure`.

If doing so remains straightforward, apply the same composition style consistently to all handlers: construct use cases in the composition root and inject them.

Do not introduce a service locator or generic dependency-injection container.

### `/help`

`/help` currently reads the help file directly from the interface layer while the application already has a `HelpContentProvider`.

If the change remains small, complete the boundary by adding a minimal help query/use case backed by the existing provider and reuse the same provider for:

* `/help`;
* empty inline-query help.

This is preferable to maintaining two file-reading paths.

If completing `/help` materially expands the change, document it explicitly as the sole remaining interface-only exception and defer it to a focused follow-up.

## Red

```text
given InlineHandler with injected application collaborators
when it handles an inline query
then no filesystem or infrastructure adapter is constructed by the handler
```

If `/help` is included:

```text
given help content supplied through the application boundary
when /help is handled
then the exact existing Markdown content is sent
without the handler opening a file
```

Add one composition-level characterization test:

```text
given production-shaped user and public-pack ports
when Stickfix wires its handlers
then every stateful handler receives application collaborators compatible with those ports
```

## Green

* construct `FileHelpContentProvider` in the composition root;
* inject required dependencies;
* remove infrastructure imports from `InlineHandler`;
* optionally move `/help` behind the existing help port.

## Refactor

If handler constructors become noisy, group dependencies only by cohesive handler role.

Do not create a generic `Services` bag containing unrelated dependencies.

## Acceptance Criteria

Required:

* `bot.handlers` does not construct persistence adapters;
* `InlineHandler` does not construct `FileHelpContentProvider`;
* infrastructure composition occurs in `bot.stickfix` or a focused composition helper;
* no application behavior moves back into Telegram handlers.

Preferred if `/help` is included:

* `/help` uses the same `HelpContentProvider` abstraction as inline help;
* no handler performs direct help-file I/O;
* every Telegram command now crosses the application boundary.

## Non-goals

* a dependency-injection framework;
* service locators;
* plugin architecture;
* changing `Stickfix(token).run()`.

## Suggested Execution Order

Complete after repository and DTO contracts have stabilized.

---

# Cycle 2.4 — Replace legacy test doubles and cover the completed use cases

## Goal

Make the test suite exercise the current architecture instead of preserving compatibility with the removed YAML/mapping seam.

## Scope

Replace application-test dependencies on:

* `StickfixDB`;
* string IDs;
* mapping-shaped user stores;
* synthetic public-user lookup.

Introduce reusable in-memory fakes under `tests/support/` or an equivalent focused location:

```text
InMemoryUserRepository
InMemoryPublicPackRepository
```

A single fake may implement both protocols when that improves a test, but its public APIs should remain the explicit port methods.

Update `tests/application/test_application_seam.py` so it no longer proves that a legacy `StickfixDB` adapter can satisfy an obsolete shape.

Add dedicated use-case coverage for the currently unrepresented files:

* `EnsureUser`;
* `SetShuffle`;
* `DeleteUser`.

Complete handler adapter coverage for:

* `/start`;
* `/shuffle`;
* `/deleteMe`;
* `/help` if Cycle 2.3 moves it through the application boundary.

Update inline-handler tests so their default test path no longer relies on a mapping-shaped `FakeUserStore` with string IDs.

## Red

Examples:

```text
given an unknown numeric user
when EnsureUser executes
then the user is created exactly once
```

```text
given an existing user
when EnsureUser executes again
then the stored state is preserved
```

```text
given each supported shuffle value
when SetShuffle executes
then the corresponding preference is persisted
```

```text
given an unsupported shuffle value
when SetShuffle executes
then an application input error is returned
and no user mutation is persisted
```

```text
given an existing user
when DeleteUser executes
then the user is removed and the result reports acknowledgement
```

```text
given a missing user
when DeleteUser executes
then the current no-op/result semantics are preserved
```

Use DDT for mode/shuffle matrices rather than duplicating near-identical examples.

## Green

Implement only missing test infrastructure and any production correction exposed by those characterization tests.

Prefer fakes over mocks.

## Refactor

* consolidate repeated fake repositories;
* keep Telegram fake objects separate from persistence fakes;
* split `test_inline_handler.py` by coherent responsibility if the new coverage would push it beyond a maintainable size:

  * inline-query adapter behavior;
  * chosen-result adapter behavior.

Do not split files merely to satisfy a numeric threshold if the tests remain cohesive.

## Acceptance Criteria

* application tests use numeric `UserId`;
* application tests use explicit repository APIs;
* no application seam test depends on `StickfixDB`;
* `EnsureUser`, `SetShuffle`, and `DeleteUser` have focused tests;
* new handler tests cover their adapter behavior;
* existing sticker, mode, and inline behavioral tests remain green;
* test doubles do not require production code to contain compatibility fallbacks.

## Non-goals

* maximizing mock interaction coverage;
* reproducing PostgreSQL inside application unit tests;
* adding PBT where a small input matrix already gives complete semantic coverage.

## Suggested Execution Order

Begin the fake migration during Cycle 2.1 and finish the broader coverage here.

---

# Cycle 2.5 — Make architectural boundaries executable

## Goal

Turn the documented dependency rule into a merge-gating contract so future changes cannot silently reintroduce Telegram or infrastructure coupling into the core.

## Scope

Add a focused architecture test, for example:

```text
tests/architecture/test_dependency_boundaries.py
```

Use the Python standard library (`ast`, `pathlib`) rather than introducing a dependency solely for this small repository.

Enforce at least:

```text
domain
    must not import Telegram, application, handlers, or infrastructure

application
    may depend on domain
    must not import Telegram, handlers, persistence infrastructure,
    SQLAlchemy, psycopg, or legacy database modules

handlers
    may depend on Telegram + application/domain
    must not import persistence infrastructure

infrastructure
    may depend on application ports + domain
```

Allow migration-only modules to depend on the isolated legacy YAML reader where explicitly required.

Also replace implementation-shape assertions in `test_application_seam.py` with checks that protect meaningful contracts rather than asserting arbitrary class organization.

## Red

```text
given the application package
when its imports are inspected
then no Telegram or infrastructure dependency crosses the application boundary
```

```text
given the domain package
when its imports are inspected
then it remains independent of application and external adapters
```

```text
given runtime handlers
when their imports are inspected
then persistence infrastructure is absent
```

Prove the test itself by temporarily introducing a representative forbidden import during TDD.

## Green

Implement the smallest AST-based dependency-policy checker.

## Refactor

* represent layer rules as small data-driven tables;
* keep diagnostics explicit:

  * importing module;
  * imported module;
  * expected dependency rule.

Avoid opaque generic architecture machinery.

## Acceptance Criteria

* dependency rules fail with actionable diagnostics;
* the test executes in the existing `pytest` quality job;
* no additional architecture-testing dependency is required;
* current allowed dependency directions are documented alongside the test;
* migration-only exceptions are narrow and explicit.

## Non-goals

* a complete static-analysis framework;
* enforcing class-level design patterns;
* scanning third-party code.

## Suggested Execution Order

Add after the production boundaries are clean so the first committed policy represents the intended end state rather than transitional exceptions.

---

# Cycle 2.6 — Add static type checking for the ports seam

## Goal

Detect structural inconsistencies such as mapping-shaped fakes being passed as `UserRepository` before runtime.

## Rationale

The current code already contains Pyright-specific annotations, but the project does not currently run a type checker in CI. Protocols, `NewType`, typed request DTOs, and repository separation provide significantly more value when their contracts are checked automatically.

This is a high-value recommendation rather than a prerequisite for the behavior-preserving refactor.

## Scope

If the existing annotation quality permits adoption without a large unrelated cleanup:

* add a supported Pyright CLI configuration;
* start with a practical checking level;
* include:

  * `bot/application`;
  * `bot/domain`;
  * focused infrastructure ports/adapters;
* make the check merge-gating once the baseline is clean.

Do not hide broad categories of diagnostics merely to obtain a green job.

If the existing legacy Telegram 13.x typings make this unexpectedly large, limit the first gate to application/domain and defer full-project typing.

## Red

Use the repository fakes to demonstrate that an object missing `PublicPackRepository` operations is rejected where the public-pack port is required.

## Green

Configure the checker and correct real type inconsistencies exposed in the changed seam.

## Refactor

Reduce suppressions in newly touched modules and document any unavoidable third-party typing boundary.

## Acceptance Criteria

If adopted in this phase:

* the application/domain type-check gate is green;
* repository fakes conform structurally to their declared ports;
* the check runs in CI;
* suppressions are focused and justified.

## Non-goals

* achieving strict typing across all legacy Telegram code in this phase;
* changing runtime behavior to satisfy the type checker;
* replacing pytest architecture tests with static typing.

## Suggested Execution Order

Perform after Cycles 2.1–2.5 so the type baseline is established against the intended architecture.

If the effort expands beyond the application seam, record it as the first follow-up rather than delaying Phase 2 closure.

---

# Cycle 2.7 — Close the phase and update the architectural contract

## Goal

Demonstrate that the current application boundary is behavior-preserving, internally consistent, and protected against regression.

## Scope

Run and gate the existing project checks:

```text
uv run ruff check
uv run ruff format --check
uv run pytest
```

Retain the existing PostgreSQL contract job:

```text
alembic upgrade head
alembic check
pytest -m integration
```

Update architecture documentation only where the final implementation differs from the current README.

In particular, ensure documentation consistently states:

```text
Telegram adapters
    ↓
application use cases
    ↓
domain + explicit ports
    ↑
infrastructure adapters
```

and that:

* PostgreSQL is the runtime backend;
* YAML is migration-only;
* user IDs are numeric;
* the public pack has an explicit port;
* application code contains no synthetic public-user persistence convention;
* all migrated commands execute through use cases;
* `/help` is either included or explicitly documented as the sole interface-only exception.

## Red

Add or update a startup/composition regression test before final wiring changes:

```text
given production-shaped user and public-pack ports
when Stickfix builds its handler graph
then every handler can be registered without legacy persistence objects
```

## Green

Make only the documentation, CI, or composition changes needed for the final contract.

## Refactor

Remove dead:

* compatibility helpers;
* outdated imports;
* obsolete comments;
* stale migration notes from application modules;
* redundant test adapters.

## Acceptance Criteria

Phase 2 is complete when:

* all stateful Telegram flows execute through application use cases;
* `/start`, `/shuffle`, and `/deleteMe` are treated as completed work, not pending work;
* sticker and inline use cases receive explicit user/public-pack ports;
* no application code contains the legacy public-pack repository bridge;
* no application test requires mapping-shaped persistence;
* application request DTOs contain only semantically required data;
* interaction context and pack mode are represented as different concepts;
* Telegram handlers contain only adapter behavior and deliberate interface-only concerns;
* application and domain modules contain no Telegram imports;
* application/domain dependency boundaries are merge-gating;
* PostgreSQL immediate-commit semantics remain unchanged;
* all existing user-visible responses and command behavior remain unchanged;
* Ruff, formatting, unit tests, and PostgreSQL integration tests pass.

---

# Deferred Work

Keep the following out of Phase 2 closure:

* redesigning PostgreSQL schema or transaction boundaries;
* YAML migration changes;
* a Unit of Work unless a later multi-repository atomic use case proves it necessary;
* event sourcing or domain events;
* a dependency-injection framework;
* replacing dataclasses with a validation framework;
* generalizing repositories beyond current use cases;
* mutation testing solely to raise a score;
* a major `python-telegram-bot` upgrade.

The `python-telegram-bot` 13.x dependency should be reviewed in a dedicated modernization phase. Moving to a modern major line is likely valuable, but its async/API changes would materially alter the Telegram adapter and should not be mixed with this behavior-preserving boundary cleanup.

---

# Priority

## Required for Phase 2 closure

1. Remove `_LegacyPublicPackRepository` and make `PublicPackRepository` explicit.
2. Clean the application request semantics.
3. Remove remaining infrastructure composition from `InlineHandler`.
4. Replace legacy mapping-shaped application fakes.
5. Cover `EnsureUser`, `SetShuffle`, and `DeleteUser`.
6. Make architectural dependency rules merge-gating.
7. Run the complete existing quality and PostgreSQL contract suites.

## High-value if bounded

* reuse `HelpContentProvider` for `/help`;
* centralize use-case construction in the composition root;
* add Pyright as an application/domain CI gate.

## Explicitly deferred

* Telegram framework modernization;
* persistence redesign;
* broader typing cleanup;
* new architectural frameworks.

---

# Suggested Execution Order

```text
2.1 Explicit user/public ports
        ↓
2.2 Request semantic cleanup
        ↓
2.3 Composition-root cleanup
        ↓
2.4 Current-contract fakes + missing tests
        ↓
2.5 Merge-gating architecture rules
        ↓
2.6 Static typing, if bounded
        ↓
2.7 Full closure and documentation
```

The minimum useful vertical increment is **Cycles 2.1 + 2.2**: after those, the application layer itself no longer carries historical YAML/mapping concepts or Telegram-shaped request data.

Cycles 2.3–2.5 then make that boundary operationally explicit and regression-resistant. Cycle 2.6 adds stronger static assurance if it can be adopted without turning this focused closure into a separate type-modernization initiative.
