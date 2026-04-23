# Phase 2 Step 1: Define the Application Seam

## Summary

Step 1 establishes the minimum application-layer seam required for the later extraction work, without moving any runtime behavior yet.

Status: implemented on 2026-04-22.

This step is purely structural. It introduces stable application contracts, bounded input/output types, and the first outbound port so later steps can extract handler behavior incrementally instead of redesigning the seam mid-migration.

Locked decisions for this step:

* DTOs are split by role, not colocated per use case
* DTO modules are `requests.py`, `results.py`, and `errors.py`
* `UserRepository` is an explicit Protocol with named methods, not mapping semantics
* success paths are result-first where practical
* exceptions are reserved for invalid input, wrong context, or genuinely exceptional application failures
* Step 1 introduces only one outbound port: `UserRepository`

No handlers, runtime wiring, persistence code, or behavior should change in this step.

Implementation notes:

* `bot/application/` now exists with the planned package skeleton
* `UserRepository` is defined as an explicit Protocol with named methods only
* request/result/error contracts are implemented and exported through `bot.application`
* `bot/__init__.py` no longer eagerly imports `bot.stickfix`, which keeps `bot.application` importable without loading Telegram
* seam-level coverage lives in `tests/application/test_application_seam.py`

---

## Goals

* create a Telegram-free application boundary
* define stable request and result types for all Phase 2 in-scope flows
* introduce the first repository port with explicit vocabulary
* make later vertical-slice extraction possible without revisiting foundational contracts
* preserve all current behavior by not migrating any logic yet

## Non-goals

* no use case implementation yet
* no handler refactors yet
* no storage adapter changes yet
* no runtime dependency injection changes yet
* no behavior tests yet beyond seam-level confidence checks
* no `HelpContentProvider` yet

---

## Deliverables

### 1. Application package skeleton

Add the initial application package with seam-defining modules only:

```text
bot/application/
    __init__.py
    requests.py
    results.py
    errors.py
    ports/
        __init__.py
        user_repository.py
    use_cases/
        __init__.py
```

Rules for this step:

* do not add concrete use case modules yet
* do not add helper modules unless strictly necessary
* do not import Telegram types anywhere under `bot/application`
* keep the package minimal and policy-oriented

### 2. Request DTOs

Define request dataclasses for the full Phase 2 scope now, so Step 2 and later steps can extract flows without reworking the seam.

Required request types:

* `AddStickerCommand`
* `GetStickersQuery`
* `DeleteStickerCommand`
* `SetModeCommand`
* `SetShuffleCommand`
* `DeleteUserCommand`
* `InlineQueryRequest`
* `ClearInlineCacheCommand`

Design rules:

* fields must be transport-agnostic
* use primitive ids, strings, booleans, small collections, and bounded enums/literals
* do not carry Telegram objects, callbacks, or rich framework types
* include only data already required by current handler behavior
* avoid speculative fields for future flows

Recommended constraint:

* each request should represent one application action
* prefer explicit names like `user_id`, `chat_type`, `query_text`, `reply_sticker_id`, `offset`, `limit`
* if chat context matters, encode it as a small bounded type rather than leaking Telegram constants

### 3. Result DTOs

Define only the result shapes that are already justified by current behavior.

Minimum result families:

* acknowledgement-style results for state-changing commands
* a sticker retrieval result for `/get`
* an inline query resolution result for inline search/default-answer behavior

Suggested types:

* `AcknowledgementResult`
* `GetStickersResult`
* `InlineQueryResult`

Design rules:

* results should model application meaning, not Telegram rendering
* do not return raw tuples or loosely shaped dictionaries
* include only metadata that current behavior already needs
* keep results additive-friendly so later steps can extend them without breaking call sites

For `InlineQueryResult`, reserve room for:

* returned sticker ids or item payloads at the application level
* explicit empty-query/default-help signaling
* `next_offset`
* any already-known cache/pagination flags needed by adapters

Avoid speculative metadata such as ranking diagnostics, pack provenance, or formatting hints unless current behavior already depends on them.

### 4. Error model

Add a small application exception hierarchy in `bot/application/errors.py`.

Initial hierarchy:

* `ApplicationError`
* `InvalidCommandInputError`
* `WrongInteractionContextError`
* `MissingStickerError`
* `MissingReplyStickerError`
* `UserNotFoundError` only if a current flow truly requires distinguishing it from “absent but tolerated”

Design rules:

* errors must express application meaning only
* do not include Telegram-facing text, markdown, or rendering hints
* do not introduce error codes yet
* do not use exceptions for ordinary branching when a result object is sufficient

Guideline:

* use result types for expected successful outcomes
* use exceptions for invalid, disallowed, or irrecoverable application situations
* keep the hierarchy shallow until multiple use cases prove a need for more granularity

### 5. User repository port

Define `UserRepository` as an explicit Protocol with named methods only.

The port should support current Phase 2 needs without reproducing the full `MutableMapping` interface or exposing storage-container semantics.

Initial responsibilities:

* retrieve a user by id
* check existence by id
* store a user
* delete a user
* retrieve the public pack if present
* ensure or create the public pack if later extraction needs that behavior

Preferred style:

* explicit verbs such as `get_user`, `has_user`, `save_user`, `delete_user`, `get_public_pack`, `ensure_public_pack`
* return `None` for absent optional lookups where appropriate instead of leaking storage exceptions
* keep names aligned with repository language, not container language

Important constraint:

* the application layer should not know or care whether the backing adapter is YAML, in-memory, or mapping-based
* Step 1 defines the protocol only; it does not force `StickfixDB` to implement it yet

---

## Design Constraints

These rules should hold for every file added in Step 1:

* no Telegram imports under `bot/application`
* no persistence-format knowledge in DTOs or ports
* no handler or adapter concerns in application types
* no speculative abstractions beyond what Step 2 immediately needs
* no behavioral migration in this step
* keep contracts small, explicit, and easy to fake in tests

---

## Type Design Notes

A few choices are worth making explicit now to prevent drift in later steps.

### Request and result DTOs should be dataclasses

Use plain dataclasses for stability, readability, and test ergonomics. Avoid introducing Pydantic or any validation framework in this phase.

### Bounded inputs should stay bounded

If the current domain already exposes enums for mode or shuffle, reusing them is acceptable as long as this does not pull Telegram concerns into the application layer.

### Prefer semantic result types over booleans

A result object with named fields is preferable to a naked `True`/`False`, especially for commands that may later need to distinguish:

* changed vs already-set
* deleted vs not-found-but-tolerated
* created vs reused

Do not over-model this in Step 1, but do leave room for it.

---

## Test Plan

Step 1 should add only seam-level tests.

### Required tests

* import tests proving the new application modules load without Telegram dependencies
* a small smoke test proving the application package can be imported in isolation
* a light protocol-target test documenting `StickfixDB` as the intended future adapter target, without modifying `StickfixDB` yet

### Explicitly out of scope

* no handler regression tests yet
* no use case behavior tests yet
* no storage adapter integration changes yet

### Compatibility expectation

* all existing tests must continue to pass unchanged

---

## Acceptance Criteria

Step 1 is complete when all of the following are true:

* `bot/application` exists with the agreed skeleton
* all Phase 2 in-scope request DTOs are defined
* the initial result DTOs are defined with non-speculative shapes
* the application error hierarchy exists
* `UserRepository` exists as an explicit Protocol with named methods only
* no code under `bot/application` imports Telegram
* no runtime behavior has changed
* no handlers, storage adapters, or wiring have been modified
* the new seam-level tests pass
* all pre-existing tests still pass unchanged

---

## Risks and Watchpoints

### 1. Over-design too early

The seam should be sufficient for Step 2, not an attempt to solve every later phase. Keep types narrow and additive-friendly.

### 2. Recreating mapping semantics by accident

Even with named methods, it is easy to preserve container-shaped thinking. Keep the repository vocabulary domain-oriented.

### 3. Result-vs-exception drift

Be disciplined about what counts as an ordinary outcome versus an actual failure, or later handlers will receive an inconsistent contract.

### 4. Hidden Telegram coupling

Chat type, inline offsets, and callback-related data can quietly leak transport assumptions into DTOs. Encode only the minimal semantics the application actually needs.

---

## Assumptions

* `HelpContentProvider` is intentionally deferred to the inline extraction step
* enum reuse from `bot.domain.user` is acceptable if it keeps inputs bounded without introducing transport coupling
* Step 1 changes no handlers, no storage adapters, and no runtime wiring
* Step 2 will extract `/setMode` first, using the seam defined here
