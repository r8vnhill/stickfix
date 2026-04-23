# Phase 2: Introduce an Application Layer and Explicit Ports

## Summary

Implement Phase 2 by introducing a small application layer that owns command/query behavior for sticker retrieval, mutation, and user settings, while keeping Telegram handlers as thin interface adapters.

Current status:

* Step 1 is implemented in `bot/application/` and covered by seam-level tests in `tests/application/test_application_seam.py`
* subsequent steps in this document remain pending

This phase is intentionally conservative:

* include `/add`, `/get`, `/deleteFrom`, inline query, `/setMode`, `/shuffle`, and `/deleteMe`
* keep `/start` and `/help` interface-only for now
* preserve current behavior, reply text, YAML persistence semantics, and runtime save strategy
* avoid unnecessary abstractions such as service locators, frameworks, or a Unit of Work

The goal is not to redesign the bot. The goal is to make behavior explicit, testable, and independent of Telegram without breaking compatibility.

---

## Goals

* move business and application decisions out of Telegram handlers
* define stable input/output types for use cases
* isolate infrastructure behind small ports
* preserve all current user-visible behavior
* make sticker flows testable with in-memory fakes

## Non-goals

* no change to `Stickfix(token).run()`
* no change to Telegram command names or response wording
* no change to YAML wire format or persistence timing
* no migration of `/start` or `/help` into the application layer in this phase
* no introduction of new third-party dependencies

---

## Architectural Direction

Phase 2 should establish this dependency rule:

```text
Telegram handlers/adapters
    -> application use cases + DTOs + application errors
        -> domain types + application ports
            -> infrastructure adapters (YAML repository, help file reader, etc.)
```

Key rule:

* the application layer must not import Telegram types
* handlers may depend on Telegram and the application layer
* infrastructure adapters may depend on filesystem/YAML details, but not on Telegram handler logic

This keeps interface concerns separate from behavior and prepares later phases for cleaner composition.

---

## Scope

### Included flows

* `/add`
* `/get`
* `/deleteFrom`
* `/setMode`
* `/shuffle`
* `/deleteMe`
* inline query flow
* inline chosen-result cache-clear flow

### Deferred flows

* `/start`
* `/help`

These remain interface-level for now, although the application layer may introduce a help-content port because inline empty-query behavior already depends on that content.

---

## Deliverables

### 1. Application package layout

Add a dedicated application package:

```text
bot/application/
    __init__.py
    dto.py
    errors.py
    ports/
        __init__.py
        user_repository.py
        help_content_provider.py
    use_cases/
        __init__.py
        add_sticker.py
        get_stickers.py
        delete_sticker.py
        set_mode.py
        set_shuffle.py
        delete_user.py
        inline_query.py
        clear_inline_cache.py
```

Notes:

* keep the package small and flat
* prefer one use case per module
* place shared application-only helpers in a small internal helper module only if duplication becomes real

### 2. Ports

Introduce small Protocol-based outbound ports.

#### `UserRepository`

Owns the user-facing storage contract required by current flows.

It should expose only the operations the application layer actually needs, not the full storage implementation surface. Prefer an explicit repository API over a mapping-shaped interface unless the current code makes that transition too disruptive.

Minimum responsibilities:

* retrieve a user by id
* check existence
* create or store a user
* delete a user
* persist pack/settings mutations through the existing in-memory objects

If preserving mapping semantics materially reduces migration risk, keep them behind the port, but the use cases should depend on named operations where possible.

#### `HelpContentProvider`

Reads help markdown/text needed for:

* inline default answer when query is empty
* future `/help` migration

Keep this port read-only and minimal.

### 3. Use cases

Add application use cases for the selected flows.

Recommended contract style:

* each use case receives one request dataclass
* each use case returns one typed result dataclass or raises a typed application error
* use cases should be callable objects or plain functions; choose the simpler style that matches the codebase

Initial set:

* `AddSticker`
* `GetStickers`
* `DeleteSticker`
* `SetMode`
* `SetShuffle`
* `DeleteUser`
* `ResolveInlineQuery`
* `ClearInlineCache`

`ClearInlineCache` can remain tiny, but making it explicit avoids leaking inline-result side effects back into handlers.

---

## Behavior Ownership

The application layer should own all non-Telegram decisions for the included flows.

### Move into use cases

* when to create or use `SF_PUBLIC`
* how to resolve the effective pack from user mode and command context
* fallback from missing `/add` tags to sticker emoji
* private-chat restriction for `/get`
* shuffle application for `/get` and inline retrieval
* inline pagination slicing and `next_offset`
* whether chosen inline results imply cache invalidation
* validation of `/setMode` arguments
* validation of `/shuffle` arguments
* delete-if-present behavior for `/deleteMe`

### Keep in handlers/adapters

* extracting data from `Update` and `CallbackContext`
* replying with Telegram text, markdown, stickers, and inline answers
* converting Telegram payloads into application requests
* translating application results/errors into current reply text and logging
* any Telegram API object construction required to send responses

A handler should become little more than:

1. parse Telegram input
2. build one request DTO
3. call one use case
4. translate the result or error into Telegram output

---

## DTOs and Type Design

Introduce stable application DTOs in `bot/application/dto.py`.

### Requests

* `AddStickerCommand`
* `GetStickersQuery`
* `DeleteStickerCommand`
* `SetModeCommand`
* `SetShuffleCommand`
* `DeleteUserCommand`
* `InlineQueryRequest`
* `ClearInlineCacheCommand`

### Results

Prefer explicit result types over raw primitives.

Examples:

* `AddStickerResult`
* `GetStickersResult`
* `DeleteStickerResult`
* `SetModeResult`
* `SetShuffleResult`
* `DeleteUserResult`
* `InlineQueryResult`
* `ClearInlineCacheResult`

Why this is preferable:

* result types make behavior explicit
* they prevent handlers from depending on hidden tuple conventions
* they leave room for metadata such as `clear_cache`, `next_offset`, `pack_used`, or `was_deleted` without breaking call sites

Use plain dataclasses and standard typing only.

Where a bounded value exists, prefer enums or literals over free-form strings, especially for mode/shuffle values.

---

## Error Model

Replace Telegram-coupled control flow inside the core behavior with typed application errors.

Suggested base hierarchy:

* `ApplicationError`

  * `InvalidCommandInputError`
  * `WrongInteractionContextError`
  * `MissingStickerError`
  * `MissingReplyStickerError`
  * `PackNotFoundError`
  * `UserNotFoundError` only if truly needed by existing semantics

Guidelines:

* errors should express application meaning, not transport details
* they should not contain preformatted Telegram text
* handlers remain responsible for mapping each error to the existing visible reply and log behavior

This keeps the application layer reusable and makes failure modes easy to test.

---

## Handler Refactor Target

`bot/handlers/*.py` stays in place, but each handler should shrink to adapter logic only.

Target shape per handler:

```text
parse Telegram input
-> create request DTO
-> invoke use case
-> translate result/error to Telegram response
```

`StickfixHandler` should retain only cross-handler adapter concerns, such as shared Telegram parsing/rendering helpers. It should no longer own sticker-routing policy, effective-pack selection, or command validation.

---

## Compatibility Constraints

This phase must preserve:

* `Stickfix(token).run()`
* existing command names
* existing YAML wire format
* existing periodic save behavior
* existing import compatibility introduced in Phase 1
* current visible bot behavior, including quirks

Intentional quirks that remain unchanged:

* `random_tag()` returns a one-item list
* sticker ordering before shuffle continues to follow current set materialization behavior

These should be captured as explicit compatibility notes in tests so they are preserved by design rather than by accident.

---

## Testing Strategy

### 1. Application unit tests

Add focused unit tests for use cases using fake in-memory adapters.

Coverage should include at least:

* `/add` stores to public pack by default
* `/add` stores to private pack when private mode is enabled
* `/add` falls back to emoji tags when explicit tags are absent
* `/get` rejects non-private chats when current behavior requires that
* `/get` resolves public/private pack behavior exactly as today
* `/deleteFrom` removes from the effective pack
* `/setMode` accepts valid modes
* `/setMode` rejects invalid modes
* `/shuffle` accepts valid values
* `/shuffle` rejects invalid values
* `/deleteMe` is safe when the user is absent
* inline query returns default help-backed answer for empty query
* inline query paginates tagged results correctly
* chosen inline result produces the expected cache-clear outcome

### 2. Thin handler regression tests

Add adapter-focused regression tests to ensure Telegram-facing behavior does not change.

At minimum cover:

* `/add`
* `/get`
* `/deleteFrom`
* `/setMode`
* `/shuffle`
* inline query

These tests should verify:

* the same reply text/markdown is emitted
* the same Telegram methods are called
* application errors are mapped to the same user-visible outcomes as before

### 3. Existing tests

* keep domain tests passing unchanged
* keep storage tests passing unchanged

This is important: Phase 2 should add a new seam, not rewrite unrelated logic.

---

## Migration Strategy

Implement this phase incrementally to reduce breakage risk.

### Step 1

Add DTOs, ports, and error types.

### Step 2

Extract one small vertical slice first, preferably `/setMode` or `/shuffle`, because they have narrow scope and clear validation rules.

### Step 3

Extract `/add`, `/get`, and `/deleteFrom`, since they exercise the main pack-resolution behavior.

### Step 4

Extract inline query and chosen-result cache clearing.

### Step 5

Refactor shared handler utilities so only Telegram adapter concerns remain.

### Step 6

Run the full test suite and confirm user-visible behavior is unchanged.

This sequence gives early validation before touching the more stateful sticker flows.

---

## Design Constraints

* prefer explicit dataclasses over loosely shaped dicts
* prefer narrow ports over generic service objects
* avoid introducing abstractions before two or more use cases genuinely need them
* keep each use case small and single-purpose
* keep Telegram types out of application modules
* do not let repository adapters leak YAML-specific details into use cases

---

## Risks and Watchpoints

* **Repository shape drift:** a mapping-like repository can keep migration easy, but may preserve too much accidental complexity. Prefer an explicit API where feasible.
* **Handler leakage:** it is easy to leave “just one more check” in handlers. Resist this unless it is purely Telegram-specific.
* **Inline flow coupling:** pagination and cache-clear behavior should be application decisions, but actual inline-response construction remains adapter work.
* **Compatibility regressions:** visible text, ordering quirks, and pack-resolution behavior must be regression-tested, not inferred.

---

## Acceptance Criteria

Phase 2 is complete when all of the following are true:

* the included flows execute through application use cases
* Telegram handlers are thin adapters with no core sticker-routing decisions
* the application layer has no Telegram imports
* typed request/result/error models exist for the included flows
* current YAML persistence semantics remain unchanged
* current user-visible behavior remains unchanged
* new application unit tests and handler regression tests pass
* existing domain and storage tests still pass unchanged

---

## Final Notes

This phase should optimise for clarity and seam creation, not abstraction density. A small, explicit application layer is enough. The main success criterion is that sticker behavior becomes independently testable and no longer lives inside Telegram handlers.
