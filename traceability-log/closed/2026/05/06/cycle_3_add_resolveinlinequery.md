# [DONE] Cycle 3: Add `ResolveInlineQuery`

## Summary

Add a Telegram-free `ResolveInlineQuery` application use case that reproduces the current inline-query lookup semantics without changing `InlineHandler` yet.

This cycle creates the application boundary that Cycle 5 will later consume. It should return only domain/application data: sticker ids, pagination metadata, help metadata, and raw help text. Telegram-specific article construction, UUID generation, parse modes, and `answer_inline_query(...)` remain handler concerns.

## Scope

Cycle 3 includes:

* inline-query resolution;
* public/private effective-pack lookup;
* empty-query help metadata;
* pagination metadata;
* cache/persistence behaviour currently triggered by inline lookup;
* application-level regression tests with in-memory fakes.

Cycle 3 explicitly excludes:

* chosen-result cache clearing;
* `InlineHandler` rewiring;
* Telegram `InlineQueryResult*` construction;
* runtime dependency wiring;
* changing command names or Telegram-visible strings;
* changing sticker ordering semantics.

## Key Changes

### Add the use case

Add:

```text
bot/application/use_cases/resolve_inline_query.py
```

with a callable use case, for example:

```python
class ResolveInlineQuery:
    ...
```

The use case should depend only on application ports and domain services.

### Reuse existing DTO names

Reuse:

* `InlineQueryRequest`
* `InlineQueryResult`

Keep the name `InlineQueryResult` for now to avoid expanding the cycle with a DTO rename. A future cleanup can introduce `ResolvedInlineQuery` as an alias or replacement once the handler is migrated.

### Refine `InlineQueryRequest`

Broaden:

```python
user_id: str | None
```

Semantics:

* `None` means “resolve as anonymous/missing user”.
* Unknown users also resolve through `SF_PUBLIC`.
* Offset should be treated as an already-normalized integer at the application boundary. Telegram’s string offset parsing remains a handler concern.

### Extend `InlineQueryResult`

Add:

```python
help_text: str | None = None
```

The result should distinguish between:

* whether the handler should include the default help article;
* the raw help content needed to build that article;
* the resolved sticker ids;
* pagination metadata.

A good DTO shape would be conceptually equivalent to:

```python
@dataclass(frozen=True)
class InlineQueryResult:
    sticker_ids: tuple[str, ...]
    next_offset: int
    show_default_help: bool = False
    help_text: str | None = None
    default_tags: tuple[str, ...] = ()
```

Use the project’s existing DTO style if it differs.

## Dependencies

Implement the use case with these dependencies:

* `UserRepository`

  * load user by id;
  * load the public user/pack;
  * save the user or pack owner whose inline lookup mutates cache state.

* `StickerPackService`

  * resolve effective private/public lookup behaviour;
  * preserve current matching, union, shuffle, and cache semantics;
  * keep sticker resolution outside the handler.

* `HelpContentProvider`

  * provide raw help text for empty inline queries at offset `0`;
  * avoid filesystem or Telegram imports in the use case.

Prefer narrow protocols for the dependencies if the existing ports are too broad.

## Behaviour Contract

`ResolveInlineQuery` must preserve the current inline-query behaviour:

* Missing repository user falls back to `SF_PUBLIC`.
* `user_id=None` falls back to `SF_PUBLIC`.
* Existing users in public mode resolve matches using the current public-mode union behaviour:

  * own cache/stickers where currently applicable;
  * public matches where currently applicable.
* Existing users in private mode resolve only the private/effective pack.
* Empty query with `offset == 0` returns:

  * `show_default_help=True`;
  * `help_text` from `HelpContentProvider`;
  * current default tags;
  * sticker results according to current behaviour.
* Empty query with `offset > 0` does not include default help.
* Non-empty query returns sticker ids only:

  * `show_default_help=False`;
  * `help_text=None`.
* Pagination uses:

  * `limit = 49`;
  * `sticker_ids[offset : offset + 49]`;
  * `next_offset = offset + 49`.
* Sticker order remains whatever the current domain/service behaviour produces. Do not introduce deterministic sorting unless existing behaviour already does so.
* The lookup persists the mutated effective pack/user after a successful resolution, matching the current cache persistence timing.

## Persistence Clarification

The most important ambiguity to remove is what exactly gets saved.

The use case should not “save the result”; it should save the user/pack owner whose sticker resolution may have mutated cache state.

A clean option is for `StickerPackService` to return a small internal resolution object, for example:

```python
@dataclass(frozen=True)
class StickerLookup:
    sticker_ids: tuple[str, ...]
    user_to_save: StickfixUser
```

Then `ResolveInlineQuery` can always call:

```python
user_repository.save_user(lookup.user_to_save)
```

This keeps the persistence decision explicit and testable without leaking Telegram concerns.

## Suggested Implementation Sequence

### 1. Add failing application tests first

Create:

```text
tests/application/use_cases/test_resolve_inline_query.py
```

Use in-memory fakes rather than mocks where possible:

* fake `UserRepository`;
* fake `StickerPackService`;
* fake `HelpContentProvider`.

Keep tests behaviour-oriented and name them around observable outcomes.

### 2. Add or adapt DTO fields

Update `InlineQueryRequest` and `InlineQueryResult` with the minimum fields needed by this cycle.

Do not rename DTOs in this cycle.

### 3. Implement the use case

Implement `ResolveInlineQuery` as a short orchestration class:

1. Resolve the requester:

   * existing user;
   * otherwise public user.
2. Resolve sticker ids through `StickerPackService`.
3. Slice results using `limit = 49`.
4. Add help metadata only for empty query at offset `0`.
5. Save the mutated/effective user returned by the sticker lookup.
6. Return `InlineQueryResult`.

Keep helper functions small, for example:

* `_resolve_request_user(...)`
* `_should_show_default_help(...)`
* `_paginate(...)`

### 4. Refactor only inside the new slice

After tests pass, clean up duplication in fakes, builders, and helper functions.

Do not touch `InlineHandler` yet.

## Test Plan

Add BDD-style tests covering the following behaviours.

### User resolution

* missing repository user falls back to public pack;
* `user_id=None` falls back to public pack;
* existing public-mode user uses current public-mode union behaviour;
* existing private-mode user resolves only private stickers.

### Help metadata

* empty query at offset `0` returns:

  * `show_default_help=True`;
  * raw help text;
  * current default tags.
* empty query at offset greater than `0` returns:

  * `show_default_help=False`;
  * `help_text=None`.
* non-empty query returns:

  * `show_default_help=False`;
  * `help_text=None`.
* `HelpContentProvider` is not called when help should not be shown.

### Pagination

* returns stickers from `offset` through `offset + 49`;
* returns `next_offset == offset + 49`;
* works when fewer than `49` stickers remain;
* works when no stickers remain.

### Persistence

* successful lookup saves the effective/mutated user through `UserRepository.save_user`;
* public fallback saves the public user if that is the cache owner;
* private lookup saves the private user;
* public-mode lookup saves the same user/pack owner the current behaviour mutates.

### Architecture seam

* no Telegram imports are introduced under `bot/application/`;
* existing application seam tests still pass.

## Focused Checks

Run:

```bash
uv run pytest tests/application/test_application_seam.py
uv run pytest tests/application/use_cases/test_resolve_inline_query.py
```

Then, before closing the cycle:

```bash
uv run pytest
uv run ruff check .
```

## Assumptions

* `InlineQueryResult` is kept temporarily for compatibility, even though `ResolvedInlineQuery` would be a clearer long-term name.
* `help_text` is the minimum DTO addition needed for Cycle 5 handler rewiring.
* The use case saves after every successful lookup to preserve current cache persistence timing.
* Telegram-specific fields remain handler concerns:

  * default article title;
  * description formatting;
  * generated UUIDs;
  * Markdown parse mode;
  * `answer_inline_query(...)` arguments.
* Any mismatch between current handler behaviour and desired future behaviour should be documented as follow-up work, not fixed in Cycle 3.
