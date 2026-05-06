# [DONE] Cycle 1: Characterize Current `InlineHandler` Behaviour

## Summary

Added handler-level regression tests for the current `InlineHandler` before extracting inline-query logic into application use cases.

This cycle was intentionally test-only. The tests describe today’s Telegram-facing behaviour exactly, including quirks such as `next_offset = offset + 49`, direct cache mutation, public-pack fallback, set-materialized sticker ordering, and the current invalid-offset failure path.

The goal was not to improve the implementation yet. The goal was to create a safety net that allows later cycles to move logic out of `InlineHandler` without accidentally changing observable bot behaviour.

Implemented in:

```text
tests/handlers/test_inline_handler.py
```

Verification:

```bash
uv run pytest tests/handlers/test_inline_handler.py
uv run pytest tests/handlers
```

## Goals

- [x] Lock current inline-query behaviour before refactoring.
- [x] Test the real `InlineHandler`, not the future use cases.
- [x] Avoid real Telegram API calls.
- [x] Avoid overfitting to unstable generated values such as UUIDs.
- [x] Preserve current quirks as explicit expectations.
- [x] Keep setup close to existing domain behaviour by using real `StickfixUser` objects where practical.

## Non-Goals

- Do not introduce `HelpContentProvider`.
- Do not introduce `ResolveInlineQuery`.
- Do not introduce `ClearInlineCache`.
- Do not add or change DTOs.
- Do not refactor `InlineHandler`.
- Do not change production code unless a minimal testability fix is absolutely unavoidable.
- Do not fix current behavioural quirks in this cycle.

## Key Changes

### 1. Add A Handler Characterization Test File

Added:

```text
tests/handlers/test_inline_handler.py
```

The file focuses on `InlineHandler` Telegram-facing behaviour.

Use test names that read as behaviour specifications, for example:

```python
def test_empty_inline_query_at_first_page_includes_help_article_before_stickers(...):
    ...

def test_non_empty_inline_query_returns_cached_sticker_results_without_help_article(...):
    ...

def test_invalid_inline_query_offset_raises_value_error_and_does_not_answer(...):
    ...
```

### 2. Use Lightweight Telegram Fakes

Real Telegram API calls are avoided. The tests use minimal fakes for only the attributes/methods the handler reads.

Recommended fakes:

```python
@dataclass
class FakeTelegramUser:
    id: int


@dataclass
class FakeInlineQuery:
    id: str
    query: str
    offset: str = "0"


@dataclass
class FakeChosenInlineResult:
    query: str


@dataclass
class FakeUpdate:
    effective_user: FakeTelegramUser | None = None
    inline_query: FakeInlineQuery | None = None
    chosen_inline_result: FakeChosenInlineResult | None = None
```

Use a capturing bot:

```python
class FakeBot:
    def __init__(self) -> None:
        self.answer_inline_query_calls: list[dict[str, object]] = []

    def answer_inline_query(self, *args: object, **kwargs: object) -> None:
        self.answer_inline_query_calls.append({"args": args, "kwargs": kwargs})
```

Use a minimal context:

```python
@dataclass
class FakeContext:
    bot: FakeBot
```

If the current handler expects dispatcher registration, add a dispatcher fake only for registration tests. Do not involve it in every behaviour test unless needed.

### 3. Use A Mapping-Compatible Store

The tests instantiate the real `InlineHandler` with a small mapping-compatible fake store.

The fake must preserve the behaviours used by the handler:

- `key in db`;
- `db[key]`;
- `db[key] = value`;
- any save/write method currently called by the handler, if applicable.

Prefer the real `StickfixDB` if it can be used without touching disk. Otherwise, use a fake that records writes so cache persistence can be asserted.

Example target shape:

```python
class FakeUserStore:
    def __init__(self) -> None:
        self.users: dict[str, StickfixUser] = {}
        self.writes: list[tuple[str, StickfixUser]] = []

    def __contains__(self, key: str) -> bool:
        return key in self.users

    def __getitem__(self, key: str) -> StickfixUser:
        return self.users[key]

    def __setitem__(self, key: str, value: StickfixUser) -> None:
        self.users[key] = value
        self.writes.append((key, value))
```

Adjust the key type to match the current implementation exactly, especially if the handler stores user ids as strings.

### 4. Call Existing Handler Methods Directly

The tests call the private handler methods directly, matching the existing pattern in `tests/handlers/test_sticker_handler.py`.

This keeps Cycle 1 small and avoids testing Telegram dispatcher internals.

The tests should exercise the current methods used for:

- answering inline queries;
- handling chosen inline results.

If method names are awkward or private, keep that awkwardness in the tests for now. Renaming or reshaping methods belongs to later cycles.

## Fixtures

Add small pytest fixtures to reduce setup duplication.

Recommended fixtures:

```python
@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def context(bot: FakeBot) -> FakeContext:
    return FakeContext(bot=bot)


@pytest.fixture
def store() -> FakeUserStore:
    return FakeUserStore()


@pytest.fixture
def handler(store: FakeUserStore) -> InlineHandler:
    return InlineHandler(store)
```

Add helper builders for domain setup:

```python
def make_user(user_id: int, *, private_mode: bool) -> StickfixUser:
    ...


def seed_stickers(user: StickfixUser, tag: str, count: int) -> list[str]:
    ...
```

Keep helpers short and behaviour-specific. Avoid a large generic fixture factory in this first cycle.

## Test Scenarios

### 1. Empty Inline Query At Offset `0`

Given:

- the effective pack contains at least one tag;
- the query text is empty;
- the offset is `"0"`.

Covered assertions:

- `answer_inline_query` is called once;
- the first positional argument is the inline query id;
- the first returned result is an `InlineQueryResultArticle`;
- the help article appears before sticker results;
- the article title is exactly:

```text
Click me for help
```

- the article description is exactly:

```text
Try calling me inline like `@stickfixbot <tag>`
```

- the article message content uses Markdown parse mode;
- subsequent sticker results are `InlineQueryResultCachedSticker`.

Avoid asserting the generated article id if it is UUID-based.

### 2. Non-Empty Inline Query

Given:

- the effective pack contains stickers for a matching tag;
- the query text is non-empty;
- the offset is `"0"`.

Covered assertions:

- no default help article is included;
- every result is an `InlineQueryResultCachedSticker`;
- each result uses the expected `sticker_file_id`;
- result ids match the expected set; order is intentionally not asserted because current resolution materializes a set.

### 3. Answer Call Arguments

For a representative inline query, assert:

```python
call = bot.answer_inline_query_calls[0]

assert call["args"][0] == inline_query.id
assert call["kwargs"]["cache_time"] == 1
assert call["kwargs"]["is_personal"] is True
assert call["kwargs"]["next_offset"] == str(offset + 49)
```

This should be covered either in a dedicated test or as shared assertions inside the main inline-query tests.

### 4. Pagination

Add focused pagination tests.

#### First Page

Given more than `49` matching stickers and `offset == "0"`:

- exactly `49` cached sticker results are returned, plus the help article only when the query is empty;
- `next_offset == "49"`.

#### Second Page

Given more than `98` matching stickers and `offset == "49"`:

- cached sticker results start from the 50th resolved sticker;
- `next_offset == "98"`;
- no default help article is repeated unless current behaviour does so.

The tests lock the current count, offset, and `next_offset` behaviour while avoiding deterministic-order assertions because current ordering comes from set materialization.

### 5. Public/Private Fallback

Characterize effective-pack resolution at the handler level.

Covered cases:

- existing private-mode user uses their own pack;
- existing public-mode user currently resolves the union of its own matching stickers and `SF_PUBLIC`;
- missing user falls back to `SF_PUBLIC`.

This can be a data-driven test if the setup remains readable.

Suggested cases:

```python
@pytest.mark.parametrize(
    ("user_exists", "private_mode", "expected_sticker_id"),
    [
        (True, True, "private-sticker"),
        (True, False, "public-sticker"),
        (False, None, "public-sticker"),
    ],
)
def test_inline_query_resolves_effective_pack(...):
    ...
```

### 6. Chosen-Result Cache Clearing

Added tests for chosen-result handling.

#### Existing User

Given:

- an existing selected user;
- that user has cached stickers.

Assert:

- chosen-result handling clears the selected user cache;
- the affected user is written back to the store;
- visible behaviour remains unchanged.

#### Missing User

Given:

- no selected user exists;
- `SF_PUBLIC` exists and has cached stickers.

Assert:

- chosen-result handling clears the public pack cache;
- the public pack is written back to the store.

Do not over-assert logging internals. It is enough to exercise the current log path unless existing tests already assert logs consistently.

### 7. Invalid Offset

Given:

- `inline_query.offset` is non-integer.

Covered assertions:

- the current exception from `int(...)` is raised, most likely `ValueError`;
- `answer_inline_query` is not called;
- no user/pack is written back as a side effect, unless current behaviour already writes before parsing.

Example:

```python
with pytest.raises(ValueError):
    handler._handle_inline_query(update, context)

assert bot.answer_inline_query_calls == []
```

## Implementation Notes

- Keep this cycle test-only.
- Prefer real domain objects over heavily mocked domain behaviour.
- Disable shuffle by default in test users/packs.
- Only enable shuffle in a dedicated characterization test if current handler behaviour depends on it.
- Seed stickers through `StickfixUser.add_sticker(...)` where possible.
- Seed cache directly only when specifically testing chosen-result cache clearing.
- Assert Telegram result classes/types and stable public attributes.
- Do not assert UUIDs or generated ids.
- Keep private-method calls because current handler tests already use that pattern.
- Use comments sparingly, mainly to mark intentionally preserved quirks.

## Suggested Test Structure

```text
tests/handlers/test_inline_handler.py

- fakes
- fixtures
- helper builders
- inline query tests
- pagination tests
- effective-pack resolution tests
- chosen-result cache-clearing tests
- invalid-offset tests
```

Suggested grouping with comments:

```python
# Inline query answering

# Pagination

# Effective pack resolution

# Chosen inline result handling

# Error characterization
```

## Test Commands

Run the new characterization tests:

```bash
uv run pytest tests/handlers/test_inline_handler.py
```

Run nearby handler tests:

```bash
uv run pytest tests/handlers
```

Optional boundary check:

```bash
uv run pytest tests/application/test_application_seam.py
```

Full suite, if the focused tests pass:

```bash
uv run pytest
```

## Acceptance Criteria

- [x] A new `tests/handlers/test_inline_handler.py` file exists.
- [x] Tests exercise the real `InlineHandler`.
- [x] Tests use fake Telegram update/context/bot objects.
- [x] No real Telegram API calls are made.
- [x] Empty-query help article behaviour is locked.
- [x] Non-empty query sticker result behaviour is locked.
- [x] `answer_inline_query(...)` arguments are locked.
- [x] Pagination behaviour is locked, including `next_offset = offset + 49`.
- [x] Public/private/missing-user fallback behaviour is locked.
- [x] Chosen-result cache clearing is locked.
- [x] Invalid offset behaviour is locked.
- [x] No application use cases or DTOs are introduced in this cycle.
- [x] Production code remains unchanged.

## Assumptions

- `InlineHandler` currently exposes private methods that can be called directly, as in existing handler tests.
- The project still uses `python-telegram-bot` objects whose result attributes can be inspected without making API calls.
- `SF_PUBLIC` is the canonical public-pack key.
- Existing quirks are intentional for this cycle and should be preserved as regression expectations.
