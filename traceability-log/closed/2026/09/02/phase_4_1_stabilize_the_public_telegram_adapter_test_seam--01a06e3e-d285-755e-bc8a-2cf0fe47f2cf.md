# Phase 4.1 — Stabilize the public Telegram adapter test seam

## Summary

Refactor **only the Telegram adapter test suite** so every handler is exercised through the callback registered with `Dispatcher`, never through name-mangled implementation methods.

This phase establishes the behavioral safety seam required before moving the Telegram adapters into a separate package.

Preserve exactly:

* production code;
* handler constructors and registration behavior;
* application DTOs and use cases;
* command names;
* Telegram-visible responses;
* Markdown modes;
* current error behavior;
* inline pagination, fallback, cache, and ordering semantics.

No production module should need modification.

## Target test boundary

Tests under `tests/handlers/` should exercise this observable path:

```text
Telegram-shaped update/context
            ↓
registered PTB handler callback
            ↓
Telegram adapter
       ↙           ↘
application DTO    Telegram response
```

They should not depend on:

```text
handler._SomeHandler__private_method(...)
```

or re-test application/domain rules behind the injected use cases.

---

## Cycle 4.1.1 — Complete the inline registration seam

### Goal

Finish the inline-handler work already started on `main`, making registered PTB callbacks the only invocation path for inline tests.

### Scope

Relevant tests:

```text
tests/handlers/test_inline_handler.py
```

Reuse the existing lookup seam for:

```python
InlineQueryHandler
ChosenInlineResultHandler
```

Migrate:

```text
_InlineHandler__inline_get
_InlineHandler__on_result
```

including the existing helper paths such as `call_inline_get`.

### Red

Change one existing mapping test to invoke the registered callback:

```text
given an InlineHandler registered with a fake dispatcher
when an inline query callback is invoked
then it maps the Telegram update into the expected InlineQueryRequest
```

Then migrate chosen-result invocation similarly:

```text
given a chosen inline result
when the registered chosen-result callback is invoked
then it sends the expected ClearInlineCacheCommand
```

The tests should fail until the helper invocation path uses the registered handlers.

### Green

Adapt the existing test helpers so they receive or retain the `FakeDispatcher` and invoke:

```python
inline_query_handler(dispatcher).callback(...)
chosen_result_handler(dispatcher).callback(...)
```

Do not add another abstraction if the existing helpers are sufficient.

### Refactor

Remove every remaining name-mangled inline invocation.

Only introduce a small immutable test harness if multiple tests genuinely need the same tuple of dispatcher, handler collaborators, and bot; otherwise keep simpler fixtures/helpers.

Prefer a shape such as:

```python
@dataclass(frozen=True, slots=True)
class InlineAdapterFixture:
    dispatcher: FakeDispatcher
    bot: FakeBot
```

rather than storing the production handler when tests do not need to inspect it.

### Acceptance criteria

* no `_InlineHandler__...` access remains under `tests/`;
* both inline callbacks are obtained through registration;
* `limit=49`, offset parsing, `cache_time=1`, `is_personal=True`, `next_offset`, Markdown and result rendering remain characterized;
* application rules are not duplicated further in handler tests.

### Non-goals

* splitting the inline test file;
* changing pagination;
* changing `49` to Telegram's maximum `50`;
* deterministic result ordering;
* changing invalid-offset behavior.

### Suggested execution order

First, because `main` already contains the registration lookup helpers and this closes the partially completed traceability work.

---

## Cycle 4.1.2 — Move utility-command tests to registered callbacks

### Goal

Exercise `/start`, `/help`, `/deleteMe`, `/setMode`, and `/shuffle` exclusively through their registered `CommandHandler` callbacks.

### Scope

Relevant utility-handler tests and their local fakes/helpers.

Cover:

```text
/start
/help
/deleteMe
/setMode
/shuffle
```

Do not call `send_help_message` directly as the primary command-flow test. `/help` should be exercised through the callback registered by `HelperHandler`, which currently wraps that function.

### Red

Start with `/start`:

```text
given HelperHandler registered with a dispatcher
when the registered /start callback receives an update
then it sends the existing welcome sticker
and invokes EnsureUser with the caller id
```

Then add the equivalent public-seam case for `/help`.

For `UserHandler`, start with one representative callback such as `/setMode` before migrating the remaining cases.

### Green

Add a narrowly scoped command lookup helper:

```python
def command_callback(
    dispatcher: FakeDispatcher,
    command: str,
) -> Callable[..., object]:
    ...
```

Locate `CommandHandler` instances using their public PTB command metadata and return their callbacks.

Use this same helper for all five commands.

### Refactor

Remove command-specific private-method invocation helpers once their last caller is migrated.

Use DDT only where scenarios genuinely share the same contract, for example:

```text
/setMode valid/invalid input
/shuffle supported argument cases
```

Do not collapse semantically different commands into one large parameterized test.

### Acceptance criteria

* utility command-flow tests never call name-mangled methods;
* `/help` is tested through its registered handler;
* welcome sticker, exact reply text, Markdown mode, DTO mapping, and current error behavior remain unchanged;
* command lookup is shared rather than reimplemented per test.

### Non-goals

* changing the lambda currently used for `/help`;
* refactoring utility production code;
* changing command argument validation.

### Suggested execution order

After inline, because it establishes the reusable `CommandHandler` lookup seam needed by the sticker adapter as well.

---

## Cycle 4.1.3 — Move sticker-command tests to registered callbacks

### Goal

Exercise `/add`, `/get`, and `/deleteFrom` through PTB registration while preserving their current adapter behavior.

### Scope

Relevant sticker-handler tests.

Migrate:

```text
_StickerHandler__add_sticker
_StickerHandler__get_stickers
_StickerHandler__delete_from
```

to registered callbacks for:

```text
/add
/get
/deleteFrom
```

### Red

Start with `/add`:

```text
given a command replying to a sticker
when the registered /add callback is invoked
then it builds the expected AddStickerCommand
and replies with the existing acknowledgement
```

Then migrate `/get`:

```text
given a private-chat /get request
when its registered callback runs
then the resulting sticker ids are sent to the Telegram chat
```

Finally migrate `/deleteFrom`.

### Green

Reuse `command_callback(...)` from Cycle 4.1.2.

Preserve existing Telegram-shaped fake updates and fake application collaborators wherever they already express the adapter contract clearly.

### Refactor

Remove obsolete helper code that existed only to invoke private methods.

Use DDT for narrowly repeated transport mappings, especially private/non-private interaction scope where the test is specifically validating Telegram → `InteractionScope` translation.

Do not reproduce the application-layer behavior for public/private pack fallback.

### Acceptance criteria

* no `_StickerHandler__...` access remains in tests;
* all three sticker commands execute through registered callbacks;
* DTO mapping, replies, sticker sends and visible error paths remain covered;
* application/domain behavior is not reimplemented in the handler suite.

### Non-goals

* changing sticker validation;
* changing `WrongInteractionContextError` semantics;
* moving Telegram validation into application;
* changing exception handling.

---

## Cycle 4.1.4 — Lock registration as an explicit adapter contract

### Goal

Ensure future adapter moves cannot silently change which PTB handlers each adapter exposes or their meaningful registration order.

### Scope

Add focused registration tests for:

```text
HelperHandler
UserHandler
StickerHandler
InlineHandler
```

Verify only externally relevant registration metadata:

* PTB handler type;
* command name where applicable;
* callback availability;
* handler order where order is significant.

Expected per-adapter registrations are currently:

```text
HelperHandler
  /start
  /help

UserHandler
  /deleteMe
  /setMode
  /shuffle

StickerHandler
  /add
  /get
  /deleteFrom

InlineHandler
  InlineQueryHandler
  ChosenInlineResultHandler
```

### Red

Add one focused registration expectation per adapter, for example:

```text
given StickerHandler
when it registers itself
then /add, /get and /deleteFrom are registered in the current order
```

### Green

Reuse the same fake dispatcher and public PTB metadata used by the callback lookup helpers.

### Refactor

Keep registration assertions separate from command behavior where doing so improves failure diagnostics.

Do not inspect:

* private callback names;
* name-mangled attributes;
* internal handler instance state.

### Acceptance criteria

* registration type and commands are explicit regression contracts;
* callback lookup and registration assertions use the same public PTB seam;
* tests fail clearly if a command disappears, is renamed, or moves relative to another order-sensitive handler.

### Non-goals

Do not assert incidental PTB object internals that have no effect on Stickfix behavior.

---

## Cycle 4.1.5 — Remove duplicated application behavior from handler tests

### Goal

Leave `tests/handlers/` responsible only for Telegram adapter behavior.

### Scope

Review the migrated tests for assertions about:

* fallback resolution;
* pagination selection;
* cache ownership;
* repository writes;
* domain sticker rules.

Where equivalent application tests already exist, remove the handler-level duplicate rather than moving or recreating it.

The handler suite should retain assertions needed to prove transport semantics, for example:

```text
raw inline offset → InlineQueryRequest.offset
application next_offset → Telegram next_offset
application sticker_ids → cached Telegram sticker results
Telegram chat type → InteractionScope
```

It should not prove how a use case computes those values.

### Red

For each candidate duplicate, first verify that an application-layer test already covers the behavior.

If coverage is missing, add it to the appropriate application suite before deleting the handler-level assertion.

### Green

Replace domain/repository-backed handler scenarios with small fake use cases returning controlled application results where appropriate.

### Refactor

Use DDT selectively for:

* inline user present / absent mapping;
* Telegram private / non-private scope mapping;
* repeated command argument mapping.

Prefer typed fake call records over raw positional dictionaries where the existing helper is otherwise hard to understand, but do not turn cleanup into a broad fake-framework rewrite.

### Acceptance criteria

* handler tests primarily assert request mapping, registration, rendering, and Telegram-visible effects;
* application suites are authoritative for pagination, fallback and cache semantics;
* no meaningful behavioral coverage is lost;
* the suite becomes smaller or at least no larger through duplicated-rule removal.

### Non-goals

* reorganizing all test directories;
* introducing a generic test framework;
* adding new dependencies;
* broad fixture cleanup unrelated to the public seam.

---

## Cycle 4.1.6 — Add the regression guard and close the phase

### Goal

Make dependence on handler-private names mechanically impossible to reintroduce unnoticed.

### Red

Add a small source-level test scanning Python files under `tests/` for the four forbidden name-mangled prefixes:

```text
_InlineHandler__
_StickerHandler__
_HelperHandler__
_UserHandler__
```

Example behavior:

```text
given the Telegram test suite
when test source files are inspected
then no test depends on name-mangled handler members
```

Prefer a Python test using `pathlib` rather than a platform-specific shell check.

### Green

Remove the final remaining occurrences.

### Refactor

Keep the guard declarative, for example:

```python
PRIVATE_HANDLER_PREFIXES = (
    "_HelperHandler__",
    "_UserHandler__",
    "_StickerHandler__",
    "_InlineHandler__",
)
```

Avoid a broad rule banning all underscore-prefixed access; some legitimate test seams may use protected members.

### Acceptance criteria

All of the following pass:

```bash
uv run pytest tests/handlers
uv run pytest tests/application
uv run pytest tests/architecture
uv run ruff check .
uv run ruff format --check .
```

Additionally:

* the automated source guard finds zero forbidden handler-private references;
* all ten Telegram callbacks are exercised through registered PTB handlers;
* no production Python module changed as part of the phase;
* no dependency changed;
* no Telegram-visible behavior changed;
* the existing inline seam traceability item is closed or superseded with an explicit completion reference;
* the Phase 4 traceability record marks 4.1 complete only after the full acceptance suite passes.

## Phase non-goals

Explicitly defer to later phases:

* extracting `stickfix-telegram`;
* creating the `uv` workspace;
* introducing callable Protocols into production handlers;
* changing handler implementations for elegance;
* PTB modernization;
* async migration;
* changing Telegram result capacity;
* deterministic pagination;
* changing exception policy.

## Suggested execution order

```text
4.1.1 inline callbacks
      ↓
4.1.2 utility command callbacks
      ↓
4.1.3 sticker command callbacks
      ↓
4.1.4 registration contracts
      ↓
4.1.5 responsibility cleanup
      ↓
4.1.6 regression guard + traceability closure
```

This version makes the phase more useful as a prerequisite for the later extraction: **the deliverable is not merely “tests no longer call private methods”; it is a stable, executable public adapter contract**. That gives Phase 4.5 a much stronger differential baseline when the Telegram package is physically moved.

---

## Implementation result

Status: implemented.

Completed:

* Inline query and chosen-result tests invoke callbacks obtained from registered PTB handlers.
* `/start`, `/help`, `/deleteMe`, `/setMode`, and `/shuffle` tests invoke registered command callbacks.
* `/add`, `/get`, and `/deleteFrom` tests invoke registered command callbacks.
* Registration order and command metadata are covered for all four handler adapters.
* Inline handler tests use controlled application results; application fallback, pagination, and cache behavior remain covered by application tests.
* Shared callback lookup helpers and an automated guard prevent name-mangled handler access from returning.
* No production module, dependency, DTO, use case, or Telegram behavior was changed.

Validation:

* Handler suite: `25 passed` using an isolated Python 3.13 environment compatible with PTB 13.x.
* Application and architecture suites: `47 passed`.
* `uvx --from ruff ruff check tests` — passed.
* `uvx --from ruff ruff format --check tests` — passed.
* The repository `uv run pytest` path remains unavailable locally because the existing `.venv` cannot be replaced on this Windows environment; the isolated handler run passed.
