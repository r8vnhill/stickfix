# [DONE] Cycle 4: Add `ClearInlineCache`

## Summary

Add a Telegram-free `ClearInlineCache` application use case for chosen inline-result cache invalidation.

This cycle introduces only the application behavior needed by the later `InlineHandler` migration. It must not rewire `InlineHandler`, construct Telegram objects, change command wording, change logging, or alter persistence format.

The use case preserves the current chosen-result semantics by resolving the same effective cache owner used by inline-query behavior, clearing all cached stickers on that owner, saving the mutated owner through `UserRepository`, and returning an explicit acknowledgement.

## Implementation Summary

- Added `ClearInlineCache` in `bot/application/use_cases/clear_inline_cache.py`.
- Updated `ClearInlineCacheCommand.user_id` to accept `str | None`.
- Exported `ClearInlineCache` from `bot.application.use_cases` and `bot.application`.
- Added `tests/application/use_cases/test_clear_inline_cache.py` with coverage for private users, public-mode users, missing users, missing effective Telegram users, missing public-pack fallback, acknowledgement return, ignored `query_text`, exact save target, and unrelated cache preservation.
- Kept `InlineHandler.__on_result` unchanged for Cycle 5.

Verified with:

```bash
uv run pytest tests/application/use_cases/test_clear_inline_cache.py
uv run pytest tests/application/test_application_seam.py
uv run ruff check bot/application tests/application/use_cases/test_clear_inline_cache.py
```

## Goals

- Add a small, test-driven application use case for clearing inline-result caches.
- Keep cache invalidation independent from Telegram.
- Reuse existing user/public-pack resolution semantics where possible.
- Preserve the current all-cache clearing behavior.
- Prepare a narrow seam for Cycle 5 handler migration.

## Non-Goals

- Do not modify `InlineHandler.__on_result`.
- Do not migrate handler wiring.
- Do not build Telegram inline-query results.
- Do not clear caches by tag or query text.
- Do not rename temporary DTOs introduced in Cycle 3.
- Do not change YAML structure, persistence behavior, command replies, or logging.

## Key Changes

- Add `bot/application/use_cases/clear_inline_cache.py`.
- Implement a callable `ClearInlineCache` use case.
- Update `ClearInlineCacheCommand.user_id` to `str | None`.
- Keep `query_text` on `ClearInlineCacheCommand` for Cycle 5 handler compatibility, but do not use it in the application behavior.
- Return `AcknowledgementResult(acknowledged=True)`.
- Export `ClearInlineCache` from `bot/application/use_cases/__init__.py`.
- Export any changed command/result surface from `bot/application/__init__.py` if the existing application seam requires it.

## Design

`ClearInlineCache` should depend on:

- `UserRepository`
  - lookup by user id;
  - lookup of the public pack;
  - saving the mutated cache owner.

It may also reuse `StickerPackService` or an existing domain helper if that already centralizes effective-pack resolution. Avoid adding new abstractions unless the current resolution logic would otherwise be duplicated.

The use case should remain small. A good target shape is:

```python
class ClearInlineCache:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def __call__(self, command: ClearInlineCacheCommand) -> AcknowledgementResult:
        cache_owner = self._resolve_cache_owner(command.user_id)
        cache_owner.remove_cached_stickers()
        self._users.save(cache_owner)
        return AcknowledgementResult(acknowledged=True)
````

The exact implementation should follow the repository API already used in `ResolveInlineQuery`.

## Effective Cache Owner Semantics

Resolve the cache owner consistently with inline-query behavior:

* If `command.user_id` belongs to an existing user whose effective pack is private, clear that user’s cache.
* If `command.user_id` belongs to an existing user whose effective pack is public, clear the public pack cache.
* If `command.user_id is None`, clear the public pack cache.
* If `command.user_id` is unknown, clear the public pack cache.
* If the public-pack fallback is required but missing, raise `UserNotFoundError`.

This avoids accidentally clearing a public-mode user’s private cache when the effective inline cache actually belongs to `SF_PUBLIC`.

## Behavior

* Clear all cached stickers on the resolved cache owner using the existing `StickfixUser.remove_cached_stickers()` behavior.
* Save exactly the mutated cache owner through `UserRepository`.
* Return `AcknowledgementResult(acknowledged=True)` after a successful save.
* Ignore `query_text`.
* Raise `UserNotFoundError` when no valid cache owner can be resolved.
* Do not import from `telegram`, `telegram.ext`, or handler modules anywhere under `bot/application/`.

## Test Plan

Add `tests/application/use_cases/test_clear_inline_cache.py`.

Use an in-memory fake repository shaped like the fake used by `test_resolve_inline_query.py`. The fake should make saved entities observable so tests can assert that the correct cache owner was saved.

### BDD Examples

Cover:

* Clears an existing private-mode user’s cache and saves that user.
* Clears the public pack cache when an existing user is in public mode.
* Clears the public pack cache when `user_id=None`.
* Clears the public pack cache when `user_id` is unknown.
* Raises `UserNotFoundError` when fallback to the public pack is required but the public pack is missing.
* Returns `AcknowledgementResult(acknowledged=True)`.
* Does not depend on `query_text`.
* Saves only the resolved cache owner, not both the requesting user and the public pack.
* Does not touch unrelated users’ cached stickers.

### Suggested Test Names

```python
def test_clears_private_user_cache_when_existing_user_is_in_private_mode() -> None: ...

def test_clears_public_cache_when_existing_user_is_in_public_mode() -> None: ...

def test_clears_public_cache_when_user_id_is_none() -> None: ...

def test_clears_public_cache_when_user_id_is_unknown() -> None: ...

def test_raises_when_public_cache_owner_is_missing() -> None: ...

def test_returns_acknowledgement_result() -> None: ...

def test_ignores_query_text() -> None: ...

def test_saves_only_the_resolved_cache_owner() -> None: ...
```

## Application Seam Tests

Update `tests/application/test_application_seam.py` only if this cycle changes exported application contracts.

Possible seam assertions:

* `ClearInlineCache` is exported from `bot.application.use_cases`.
* `ClearInlineCacheCommand` accepts `user_id=None`.
* `AcknowledgementResult` remains available from the expected application export surface.
* No application module imports Telegram.

## Commands to Run

```bash
uv run pytest tests/application/use_cases/test_clear_inline_cache.py
uv run pytest tests/application/test_application_seam.py
uv run pytest tests/application/use_cases
```

If the repository already has a broader application or full test command, run that after the focused checks:

```bash
uv run pytest tests/application
uv run pytest
```

## Acceptance Criteria

* `ClearInlineCache` exists and is Telegram-free.
* `ClearInlineCacheCommand.user_id` supports `str | None`.
* Existing users, missing users, and missing Telegram users resolve to the correct effective cache owner.
* Public-pack fallback failure raises `UserNotFoundError`.
* Cache clearing uses `remove_cached_stickers()` and preserves current all-cache semantics.
* The mutated cache owner is saved exactly once.
* `query_text` does not affect behavior.
* The use case returns `AcknowledgementResult(acknowledged=True)`.
* No handler behavior changes are included in this cycle.

## Assumptions

* Cycle 4 is application-only.
* `InlineHandler.__on_result` remains unchanged until Cycle 5.
* `InlineQueryResult` keeps its temporary Cycle 3 name.
* Cache clearing means clearing all cached stickers, not tag-specific invalidation.
* The public pack is represented by the existing `SF_PUBLIC` user/pack model.
* `UserRepository` remains the persistence boundary for both regular users and the public pack.
