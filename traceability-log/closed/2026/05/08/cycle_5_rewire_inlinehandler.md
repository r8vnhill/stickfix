# [COMPLETED] Cycle 5: Rewire `InlineHandler`

## Completion Status

✅ Completed on 2026-05-09. All goals achieved, all tests passing (118 tests, 100% pass rate).

## Summary

Rewired `InlineHandler` so Telegram-facing code delegates inline-query resolution and chosen-result cache invalidation to the application layer.

This cycle completes the inline-query extraction started in earlier cycles. `InlineHandler` now keeps ownership of Telegram-specific concerns only: reading Telegram updates, parsing Telegram pagination offsets, constructing Telegram inline result objects, answering inline queries, and preserving current logging/error semantics.

No user-visible behaviour, storage format, command names, reply wording, pagination semantics, cache behaviour, or YAML persistence behaviour changed.

## Goals

* Make `InlineHandler` a thin interface adapter.
* Delegate inline-query lookup to `ResolveInlineQuery`.
* Delegate chosen-result cache clearing to `ClearInlineCache`.
* Preserve the existing Telegram API response shape exactly.
* Keep `bot/application/` Telegram-free.
* Preserve current exception handling semantics:

  * inline-query errors are logged and re-raised;
  * chosen-result errors are logged and swallowed.

## Non-Goals

* Do not change inline-query pagination semantics.
* Do not change sticker shuffle/cache behaviour.
* Do not change help article wording or shape.
* Do not change public/private fallback rules.
* Do not change handler registration.
* Do not introduce Telegram imports into application use cases.
* Do not alter YAML structure, save cadence, or repository persistence semantics.

## Key Changes

### 1. Inject application use cases into `InlineHandler`

Update `InlineHandler.__init__` to accept optional use cases:

```python
resolve_inline_query: ResolveInlineQuery | None = None
clear_inline_cache: ClearInlineCache | None = None
```

When not injected, construct production defaults from existing infrastructure:

```python
repository = StickfixUserRepository(user_db)
help_provider = FileHelpContentProvider(Path(HELP_PATH))
pack_service = StickerPackService()

self._resolve_inline_query = resolve_inline_query or ResolveInlineQuery(
    repository=repository,
    help_content_provider=help_provider,
    sticker_pack_service=pack_service,
)

self._clear_inline_cache = clear_inline_cache or ClearInlineCache(
    repository=repository,
    sticker_pack_service=pack_service,
)
```

Prefer a small private factory/helper if constructor wiring becomes noisy, for example:

```python
def _build_default_inline_use_cases(user_db: StickfixDB) -> InlineUseCases:
    ...
```

This keeps `__init__` short and easier to test.

### 2. Keep handler registration unchanged

Do not change the dispatcher registration contract:

```python
InlineQueryHandler(self.__inline_get)
ChosenInlineResultHandler(self.__on_result)
```

This preserves current runtime integration with `python-telegram-bot`.

## Handler Behaviour

### `__inline_get`

The handler should:

1. Read Telegram data from the update:

   * `update.inline_query`
   * `inline_query.query`
   * `inline_query.offset`
   * `update.effective_user`

2. Parse the offset exactly as today:

```python
offset = int(0 if not inline_query.offset else inline_query.offset)
```

Keep this parsing in the handler because offset strings are Telegram transport data.

3. Convert the Telegram user into the application contract safely:

```python
user_id = str(user.id) if user is not None else None
```

Avoid:

```python
str(user.id) or None
```

because it raises before the fallback when `user` is `None`.

4. Build the application request:

```python
request = InlineQueryRequest(
    user_id=user_id,
    query_text=inline_query.query,
    offset=offset,
    limit=49,
)
```

5. Call `ResolveInlineQuery`.

6. Convert the application result into Telegram inline result objects:

   * convert `show_default_help`, `default_tags`, and `help_text` into the existing help article shape;
   * convert every returned sticker id into:

```python
InlineQueryResultCachedSticker(
    id=str(uuid4()),
    sticker_file_id=sticker_file_id,
)
```

7. Answer the inline query with the existing arguments:

```python
await inline_query.answer(
    results=results,
    cache_time=1,
    is_personal=True,
    next_offset=str(result.next_offset),
)
```

or preserve the current equivalent call style if the code currently uses `context.bot.answer_inline_query(...)`.

8. Preserve current exception behaviour:

   * log through `unexpected_error`;
   * re-raise the exception.

### `__on_result`

The handler should:

1. Read:

   * `update.effective_user`
   * `update.chosen_inline_result.query`

2. Convert the Telegram user safely:

```python
user_id = str(user.id) if user is not None else None
```

3. Build the command:

```python
command = ClearInlineCacheCommand(
    user_id=user_id,
    query_text=chosen_inline_result.query,
)
```

4. Call `ClearInlineCache`.

5. Preserve the current success log text:

```python
Answered inline query for {query}
```

6. Preserve current exception behaviour:

   * log through `unexpected_error`;
   * swallow the exception.

## Logic to Remove from `InlineHandler`

After rewiring, remove these responsibilities from the handler:

* direct public/private pack resolution;
* unknown-user fallback logic;
* direct access to public pack constants except through application/infrastructure wiring;
* inline sticker lookup;
* pagination over stickers;
* sticker shuffle/cache mutation;
* chosen-result cache clearing logic;
* direct help-file reading;
* any direct mutation of user/sticker-pack domain state.

The handler should only translate between Telegram objects and application DTOs.

## Suggested Structure

A useful shape for the final handler is:

```python
class InlineHandler(Handler):
    def __init__(
        self,
        dispatcher: Dispatcher,
        user_db: StickfixDB,
        resolve_inline_query: ResolveInlineQuery | None = None,
        clear_inline_cache: ClearInlineCache | None = None,
    ) -> None:
        ...

    async def __inline_get(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        ...

    async def __on_result(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        ...

    def _build_inline_request(self, update: Update) -> InlineQueryRequest:
        ...

    def _build_clear_cache_command(
        self,
        update: Update,
    ) -> ClearInlineCacheCommand:
        ...

    def _to_telegram_results(
        self,
        result: InlineQueryResult,
    ) -> list[InlineQueryResultArticle | InlineQueryResultCachedSticker]:
        ...

    def _build_help_article(
        self,
        result: InlineQueryResult,
    ) -> InlineQueryResultArticle:
        ...
```

Keep helpers small and private. This makes the transport mapping independently testable without moving Telegram types into the application layer.

## Tests

### Handler tests

Update `tests/handlers/test_inline_handler.py` to prefer fake use cases over repository/domain fakes when testing handler wiring.

Assert that `__inline_get`:

* builds `InlineQueryRequest` from Telegram values;
* passes `user_id=str(user.id)` when `effective_user` exists;
* passes `user_id=None` when `effective_user` is absent;
* parses offset with the current expression;
* raises `ValueError` for invalid offsets;
* does not answer the query when offset parsing fails;
* does not call `ResolveInlineQuery` when offset parsing fails;
* maps default-help application results to the existing `InlineQueryResultArticle` shape;
* preserves title, description/content shape, parse mode, and id semantics for the help article;
* maps sticker ids to `InlineQueryResultCachedSticker`;
* uses generated UUIDs for Telegram result ids;
* calls `answer_inline_query(...)` or `inline_query.answer(...)` with:

  * same inline query id;
  * same result list shape;
  * `cache_time=1`;
  * `is_personal=True`;
  * `next_offset=str(result.next_offset)`;
* logs through `unexpected_error` and re-raises on unexpected errors.

Assert that `__on_result`:

* builds `ClearInlineCacheCommand` from Telegram values;
* passes `user_id=None` when `effective_user` is absent;
* passes `query_text=chosen_inline_result.query`;
* calls `ClearInlineCache`;
* preserves the current success log text;
* logs through `unexpected_error` and swallows unexpected errors.

### Production wiring tests

Add a narrow seam test for default construction only if existing tests do not cover it.

The goal is not to deeply test `ResolveInlineQuery` or `ClearInlineCache` through the handler, but to ensure that default construction still works when use cases are not injected.

Possible assertion:

* constructing `InlineHandler(dispatcher, user_db)` registers the same handlers and does not require explicit use-case injection.

Avoid testing private dependency internals unless there is already a stable seam for that.

### Application tests

Keep existing application use-case tests unchanged, except for import paths if needed.

The application layer should already own tests for:

* public/private fallback;
* missing-user behaviour;
* empty-query help resolution;
* sticker pagination;
* cache clearing;
* repository save behaviour.

## Recommended TDD Order

1. **Lock request mapping**

   * Inject a fake `ResolveInlineQuery`.
   * Assert the exact `InlineQueryRequest`.

2. **Lock absent-user behaviour**

   * Assert `user_id=None`.

3. **Lock offset behaviour**

   * Assert valid offset parsing.
   * Assert invalid offset raises before use-case invocation.

4. **Lock Telegram result mapping**

   * Help article case.
   * Sticker result case.
   * `answer_inline_query` arguments.

5. **Lock chosen-result command mapping**

   * Inject fake `ClearInlineCache`.
   * Assert `ClearInlineCacheCommand`.

6. **Lock error behaviour**

   * Inline query: log and re-raise.
   * Chosen result: log and swallow.

7. **Refactor handler internals**

   * Extract private mapping helpers only after tests pass.
   * Remove old lookup/cache/help-file logic.

8. **Run broader regression suite.**

## Verification Commands

Run focused tests first:

```bash
uv run pytest tests/handlers/test_inline_handler.py
uv run pytest tests/application/test_application_seam.py
uv run pytest tests/application/use_cases
```

Then run broader checks:

```bash
uv run pytest tests/handlers
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Risks and Mitigations

### Risk: accidental `None` user regression

Use explicit safe conversion:

```python
str(user.id) if user is not None else None
```

Add tests for both inline queries and chosen results with no `effective_user`.

### Risk: handler starts retesting application behaviour

Keep handler tests focused on transport mapping and Telegram response shape. Do not duplicate use-case tests for pack resolution, fallback, pagination, or cache mutation.

### Risk: production wiring becomes too large

Use a small default-use-case factory or container-style helper to keep `InlineHandler.__init__` readable.

### Risk: help article shape changes accidentally

Add structural assertions for the generated `InlineQueryResultArticle`, including title, content, parse mode, and result id behaviour.

### Risk: UUID assertions become brittle

Patch UUID generation at the handler seam, or assert only that each sticker result gets a non-empty string id unless existing tests already patch UUIDs.

## Assumptions

* `ClearInlineCacheCommand.query_text` is retained for compatibility/logging context even if unused by the use case.
* `InlineQueryRequest.limit` remains `49`.
* Help article title, Markdown parse mode, UUID generation, and Telegram inline-result classes remain in `InlineHandler`.
* Application DTOs remain Telegram-free.
* `StickerPackService` remains shared between inline resolution and cache clearing in default production wiring.
* No user-visible behaviour changes are intended.

## Implementation Completion Notes

### What Was Changed

1. **`bot/handlers/inline.py`** - Complete refactor:
   - Replaced all business logic with delegation to application layer
   - Added `resolve_inline_query` and `clear_inline_cache` use case injectors
   - Created `_build_default_resolve_inline_query()` and `_build_default_clear_inline_cache()` factories
   - Refactored `__inline_get()` to:
     - Parse Telegram data safely (`user_id = str(user.id) if user is not None else None`)
     - Build `InlineQueryRequest` with explicit offset parsing
     - Delegate to use case
     - Convert result to Telegram objects via `_build_help_article()`
   - Refactored `__on_result()` to:
     - Build `ClearInlineCacheCommand` and delegate
     - Preserve logging ("Answered inline query for {query}")
     - Preserve exception handling (log and swallow)
   - Removed `__send_default_answer()` and `_get_sticker_list()` calls (moved to application)

2. **`tests/handlers/test_inline_handler.py`** - Updated for use case injection:
   - Added `FakeResolveInlineQuery` and `FakeClearInlineCache` test doubles
   - Updated `FakeUserStore` to support `.get()` method
   - Updated `make_user()` to use string user IDs (aligning with `StickfixDB[str, StickfixUser]`)
   - Updated `make_handler()` to accept optional use cases
   - Added 7 new tests focused on request/command mapping:
     - `test_inline_query_builds_request_with_user_id_when_effective_user_exists()`
     - `test_inline_query_builds_request_with_none_user_id_when_effective_user_is_none()`
     - `test_inline_query_builds_request_with_query_text_and_offset()`
     - `test_inline_query_builds_help_article_from_application_result()`
     - `test_chosen_result_builds_command_with_user_id_when_effective_user_exists()`
     - `test_chosen_result_builds_command_with_none_user_id_when_effective_user_is_none()`
     - `test_chosen_result_builds_command_with_query_text()`
   - Kept all original behavioral tests intact

3. **`traceability-log/cycle_5_rewire_inlinehandler.md`** - Marked as completed

### Key Implementation Details

- **User ID Conversion**: Handler converts Telegram `user.id` (int) to string for application request
- **Key Type Fix**: Test helper `make_user()` updated to store users with string keys (`store[str(user_id)]`) to match `StickfixDB` contract
- **Effective Pack Resolution**: Handler remains Telegram-aware; application layer determines whether to use user or public pack
- **Error Semantics**: Preserved exactly as specified:
  - Inline query: logs via `unexpected_error()`, re-raises
  - Chosen result: logs via `unexpected_error()`, swallows (no re-raise)
- **Help Article**: Generated fresh from `InlineQueryResult` with fallback to "help" tag if no default tags available

### Test Results

All 118 tests passing:
- `tests/handlers/test_inline_handler.py`: 17/17 ✅
- `tests/application/use_cases/test_resolve_inline_query.py`: 11/11 ✅
- `tests/application/use_cases/test_clear_inline_cache.py`: 8/8 ✅
- All other tests: 82/82 ✅

### Code Quality

- Ruff checks: 0 issues in modified files
- Format check: Applied (imports reorganized)
- No new Telegram imports in `bot/application/` ✅

### Behavioral Verification

All existing behaviors preserved:
- ✅ Public/private fallback
- ✅ Empty query + first page → help article + default stickers
- ✅ Pagination (49 stickers per page, correct next_offset)
- ✅ Cache clearing on chosen result
- ✅ Invalid offset handling
- ✅ Missing user fallback to public pack
