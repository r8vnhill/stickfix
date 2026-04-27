# [PLAN] Step 3: Extract Sticker Commands Into Application Use Cases

Status: implemented.

Implementation notes:

* `AddSticker`, `GetStickers`, and `DeleteSticker` now live in `bot/application/use_cases/`.
* `StickerPackService` lives in `bot/domain/services/` and owns Telegram-free effective-pack resolution, link/unlink behavior, and sticker lookup.
* `StickerHandler` delegates sticker command behavior to use cases while preserving Telegram validation, reply wording, sticker sending, and handled-error logging.
* Explicit `AddStickerResult` and `DeleteStickerResult` DTOs were added alongside `GetStickersResult`.
* `tests/__init__.py` was added so existing storage tests can import `tests.support` consistently during collection.
* `pyproject.toml` now tells pytest to ignore generated/runtime directories such as `worktmp/`, so `uv run pytest` works from the repository root.

## Summary

Extract `/add`, `/get`, and `/deleteFrom` from `StickerHandler` into Telegram-free application use cases while preserving current Telegram-visible behaviour, command names, YAML persistence format, save timing, and public/private sticker-pack semantics.

This step introduces a small sticker-pack application slice:

* pure domain logic for resolving and mutating effective sticker packs;
* application use cases for command orchestration;
* thin Telegram handlers that only translate Telegram input/output;
* regression tests that lock current behaviour before and after extraction.

The slice should be implemented together, but migrated through small TDD sub-cycles: `/add`, `/get`, then `/deleteFrom`.

---

## Design Goals

* Keep `bot.application` free of `telegram` imports.
* Keep handlers as interface adapters, not business-logic owners.
* Keep persistence behind `UserRepository`.
* Preserve the legacy YAML object shape.
* Preserve current user/public-pack behaviour exactly.
* Avoid introducing richer repository methods in this step.
* Make result DTOs describe outcomes, not Telegram messages.
* Keep sticker selection/shuffle/cache behaviour stable, but avoid putting stateful cache concerns into the pure domain service unless that cache is already part of the domain object model.

---

## Proposed Structure

```text
bot/
  domain/
    services/
      sticker_pack_service.py
  application/
    use_cases/
      add_sticker.py
      get_stickers.py
      delete_sticker.py
    dto/
      sticker_commands.py
      sticker_results.py
    errors.py
  presentation/
    telegram/
      sticker_handler.py
```

Exact paths can follow the repository’s current conventions, but the dependency direction should be:

```text
Telegram Handler → Application Use Case → Domain Service / Repository Port → Domain Model
```

No import from `telegram` should appear below the presentation layer.

---

## Domain Service

Add a Telegram-free domain service, for example `StickerPackService`, responsible for pure pack behaviour.

It should centralize:

* resolving the effective target pack from:

  * the current user;
  * the `SF_PUBLIC` user/pack;
  * the user’s `private_mode`;
* adding sticker links to a pack;
* removing sticker links from a pack;
* resolving sticker ids for requested tags according to current pack semantics.

The service should not:

* load or save users;
* create `SF_PUBLIC` by itself;
* inspect Telegram objects;
* decide Telegram replies;
* log Telegram-specific warnings;
* own persistence/cache side effects unless the existing cache is already stored in domain objects.

If `/get` currently mutates a cache or shuffle state that is persisted, keep that mutation in the application use case and save exactly where the old handler saved. If the shuffle/cache is purely in-memory or handler-owned, introduce a small application-level selector/collaborator rather than bloating the domain service.

Suggested responsibility split:

```text
StickerPackService
  - resolve_effective_pack(...)
  - add_sticker(...)
  - delete_sticker(...)
  - find_stickers(...)

GetStickers
  - validates private-chat context
  - loads user/public pack
  - delegates lookup
  - preserves shuffle/cache/save timing
```

---

## Application Use Cases

Add three use cases:

* `AddSticker`
* `GetStickers`
* `DeleteSticker`

They should depend on:

* `UserRepository`
* `StickerPackService`
* optional selector/cache collaborator if needed for `/get`

They should not depend on:

* `telegram.Update`
* `telegram.ext.CallbackContext`
* Telegram stickers
* Telegram chat types
* Telegram reply APIs

---

## Request DTOs

Reuse the existing request DTOs:

* `AddStickerCommand`
* `GetStickersQuery`
* `DeleteStickerCommand`

However, make the command boundary explicit.

A good application command should contain already-extracted primitive/domain values, for example:

```text
AddStickerCommand
  - user_id
  - sticker_id
  - tags
  - emoji
```

```text
GetStickersQuery
  - user_id
  - chat_type / interaction_context
  - tags
```

```text
DeleteStickerCommand
  - user_id
  - sticker_id
  - tags
```

The handler should remain responsible for reading Telegram’s reply/sticker shape. The use case may still validate missing or blank primitive values defensively, but it should not receive Telegram objects.

---

## Result DTOs

Add explicit result DTOs:

* `AddStickerResult`
* `DeleteStickerResult`
* keep or extend `GetStickersResult`

Suggested shape:

```text
AddStickerResult
  - sticker_id
  - effective_tags
  - changed
```

```text
DeleteStickerResult
  - sticker_id
  - effective_tags
  - changed
```

```text
GetStickersResult
  - sticker_ids
```

`changed` is useful for tests and future observability, but the handler must still preserve current Telegram-visible behaviour. For example, `/add` still replies `"Ok!"` even when `changed == False`.

Avoid storing reply text such as `"Ok!"` inside application results unless the project already has an established acknowledgement DTO pattern. The application should express what happened; the handler should translate that into Telegram output.

---

## Application Errors

Use explicit application errors for command-level failures:

* `WrongInteractionContextError`

  * `/get` used outside private chats.
* `InvalidCommandInputError`

  * invalid or incomplete command arguments.
* `MissingStickerReplyError`

  * if the application receives a command without a sticker id after handler extraction.
* optional `StickerPackNotFoundError`

  * only if the existing behaviour distinguishes missing packs from empty results.

Recommended boundary:

* Telegram-specific shape errors are detected in the handler when possible.
* Application errors cover invalid command DTO state.
* Handler maps application errors to existing replies/logging.

This keeps the use cases robust without making them Telegram-aware.

---

## Behaviour Contract

### `/add`

Preserve current behaviour:

* requires replying to a sticker;
* ensures `SF_PUBLIC` exists before sticker mutation;
* uses explicit tags when provided;
* falls back to sticker emoji when no tags are provided;
* if no tags and no emoji exist, performs the same no-op as today;
* always replies exactly:

```text
Ok!
```

even when no tags/emoji are available.

Pack behaviour:

* public-mode users add to `SF_PUBLIC`;
* private-mode users add to their private pack;
* YAML persistence and save timing remain unchanged;
* user creation behaviour remains unchanged.

Important clarification:

`SF_PUBLIC` creation should remain part of `/add`, not a global invariant for every sticker command.

---

### `/get`

Preserve current behaviour:

* only works in private chats;
* non-private chats reply exactly:

```text
This command only works in private chats.
```

* resolves the requesting user’s pack when available;
* falls back to `SF_PUBLIC` according to current semantics;
* returns sticker ids through `GetStickersResult`;
* handler sends each sticker id through Telegram;
* preserves current ordering, shuffle, cache, and save-timing behaviour.

The use case should return data only. It should not send stickers.

---

### `/deleteFrom`

Preserve current behaviour:

* requires replying to a sticker;
* removes the sticker from the effective pack using the current public/private mode;
* preserves current no-success-reply behaviour;
* preserves current behaviour when the sticker/tag is absent;
* preserves YAML persistence and save timing.

The handler should continue to decide whether any Telegram reply is sent. For now, successful deletion should remain silent if that is the current behaviour.

---

## Implementation Plan

### 1. Add Characterisation Tests First

Before moving logic, add or tighten tests around the current `StickerHandler` behaviour.

Lock:

* exact replies;
* missing reply/sticker behaviour;
* public/private pack selection;
* `SF_PUBLIC` creation during `/add`;
* `/get` rejection outside private chats;
* `/deleteFrom` no-success-reply behaviour;
* YAML save timing if observable;
* shuffle/cache behaviour if observable.

This protects the extraction from accidental semantic changes.

---

### 2. Introduce Domain Service

Add `StickerPackService` with pure unit tests.

Cover:

* public-mode effective pack resolution;
* private-mode effective pack resolution;
* missing private pack fallback if current behaviour allows it;
* missing `SF_PUBLIC` handling;
* add mutation;
* delete mutation;
* empty tag list behaviour;
* duplicate tags if currently relevant.

Use DDT for the public/private resolution matrix.

Possible BDD-style examples:

```text
StickerPackService
  resolves the public pack for public-mode users
  resolves the private pack for private-mode users
  falls back to the public pack when current behaviour requires it
  links a sticker to every effective tag
  ignores empty tag input according to the legacy contract
  unlinks only from the effective pack
```

---

### 3. Extract `/add`

Implement `AddSticker`.

Use case responsibilities:

* load or create the requesting user according to current behaviour;
* ensure `SF_PUBLIC` exists before mutation;
* normalize effective tags:

  * explicit tags first;
  * emoji fallback second;
  * empty/no-op last;
* delegate pack mutation to the domain service;
* save through `UserRepository.save_user(...)` exactly as before;
* return `AddStickerResult`.

Then update `StickerHandler.add` to:

* inspect Telegram reply/sticker shape;
* build `AddStickerCommand`;
* call `AddSticker`;
* reply `"Ok!"`;
* preserve old logging/error mapping.

---

### 4. Extract `/get`

Implement `GetStickers`.

Use case responsibilities:

* reject non-private interaction context with `WrongInteractionContextError`;
* load the requesting user;
* load `SF_PUBLIC` if needed;
* resolve the effective pack according to the existing fallback semantics;
* preserve current selection/shuffle/cache behaviour;
* return `GetStickersResult`.

Then update `StickerHandler.get` to:

* build `GetStickersQuery`;
* call `GetStickers`;
* map `WrongInteractionContextError` to the exact existing reply;
* send returned sticker ids using Telegram APIs.

---

### 5. Extract `/deleteFrom`

Implement `DeleteSticker`.

Use case responsibilities:

* load the requesting user;
* load `SF_PUBLIC` if required by current public/private semantics;
* delegate deletion to the domain service;
* save through `UserRepository.save_user(...)` exactly as before;
* return `DeleteStickerResult`.

Then update `StickerHandler.delete_from` to:

* inspect Telegram reply/sticker shape;
* build `DeleteStickerCommand`;
* call `DeleteSticker`;
* preserve current silent success behaviour;
* preserve current error replies/logging.

---

### 6. Clean Up Handler

After all three commands are extracted, `StickerHandler` should contain only:

* Telegram input extraction;
* Telegram shape validation;
* DTO construction;
* use-case invocation;
* Telegram output mapping;
* logging tied to Telegram interaction failures.

It should no longer own pack resolution, mutation, fallback, or persistence orchestration.

---

## Test Plan

### Application Seam Test

Keep this passing:

```bash
uv run pytest tests/application/test_application_seam.py
```

It should verify that importing `bot.application` does not import `telegram`.

---

### Domain Service Tests

Add focused BDD tests for `StickerPackService`.

Cover:

* effective pack resolution;
* public/private mode matrix;
* missing pack fallback;
* add mutation;
* delete mutation;
* empty tag handling;
* duplicate/idempotent mutation if supported by current model.

Use DDT for repeated public/private/tag combinations.

---

### Use-Case Tests

Use in-memory repository fakes.

#### `AddSticker`

Cover:

* creates/uses `SF_PUBLIC` by default;
* writes to private pack when private mode is enabled;
* uses explicit tags when present;
* falls back to sticker emoji when tags are absent;
* no tags and no emoji preserves current `"Ok!"` no-op behaviour;
* saves through `UserRepository.save_user(...)` with unchanged timing;
* does not import Telegram.

#### `GetStickers`

Cover:

* rejects non-private chat with `WrongInteractionContextError`;
* resolves user pack when present;
* falls back to `SF_PUBLIC` when current behaviour requires it;
* returns empty result when current behaviour does;
* preserves ordering/shuffle/cache behaviour;
* saves only if the current cache/shuffle behaviour already saves.

#### `DeleteSticker`

Cover:

* removes from the public pack in public mode;
* removes from the private pack in private mode;
* preserves current behaviour when sticker/tag is absent;
* saves through `UserRepository.save_user(...)` with unchanged timing;
* returns `DeleteStickerResult` without implying a Telegram reply.

---

### Handler Regression Tests

Use fake use cases.

Cover:

* correct DTOs are built for `/add`;
* correct DTOs are built for `/get`;
* correct DTOs are built for `/deleteFrom`;
* existing replies are preserved exactly;
* `/get` non-private error maps to the existing message;
* `/add` success maps to `"Ok!"`;
* `/deleteFrom` success remains silent;
* sticker sending remains handler-owned;
* application errors map to the same Telegram-visible behaviour as before.

---

## Validation Commands

Run incrementally:

```bash
uv run pytest tests/application/test_application_seam.py
uv run pytest tests/domain
uv run pytest tests/application/use_cases
uv run pytest tests/presentation/telegram/test_sticker_handler.py
uv run pytest
```

Adjust paths to the repository’s actual test layout.

---

## Assumptions

* `SF_PUBLIC` creation remains specific to `/add`.
* The new domain service depends only on domain objects.
* Repositories remain coarse-grained for this step.
* YAML persistence format does not change.
* Save timing does not change.
* Handler-side Telegram shape checks remain in the handler.
* Application DTO validation is defensive but Telegram-free.
* Result DTOs encode outcomes, not localized or Telegram-specific reply text.
* `/get` shuffle/cache behaviour is preserved, but its stateful parts remain in the application layer unless already modelled in the domain.

---

## Main Risks And Mitigations

### Risk: Domain service becomes an application service

If it creates users, loads repositories, saves users, or knows command names, it is no longer a domain service.

Mitigation: keep repository access only in use cases.

---

### Risk: Handler extraction changes visible replies

Small wording changes can break user-visible compatibility.

Mitigation: assert exact reply strings in handler regression tests.

---

### Risk: `/get` shuffle/cache behaviour is accidentally simplified

Selection behaviour is easy to change while “cleaning up”.

Mitigation: add characterisation tests before moving `/get`.

---

### Risk: `SF_PUBLIC` creation becomes too broad

Creating `SF_PUBLIC` in every command may change persistence side effects.

Mitigation: keep creation inside `AddSticker` only unless current code already does otherwise.

---

### Risk: Result DTOs leak Telegram concerns

DTOs like `reply_text` or `should_send_sticker` couple the application layer to Telegram.

Mitigation: return domain/application outcomes and keep output decisions in the handler.
