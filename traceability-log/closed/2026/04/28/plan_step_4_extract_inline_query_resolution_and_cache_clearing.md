# [PLAN] Step 4: Extract Inline Query Resolution And Cache Clearing

## Summary

Extract inline query lookup and chosen-result cache clearing from `InlineHandler` into Telegram-free application use cases.

Current status:

- Cycle 1 is implemented in `tests/handlers/test_inline_handler.py`.
- Characterization found two compatibility quirks that later cycles must preserve unless the maintainer explicitly chooses otherwise:
  - inline sticker result ordering follows current set materialization and must not be made deterministic accidentally;
  - public-mode existing users currently resolve matching stickers from both their own pack and `SF_PUBLIC`.

After this step, `InlineHandler` should only:

- read Telegram update/context objects;
- parse Telegram-specific values such as inline query ids and offsets;
- call application use cases with plain DTOs;
- convert application results into `InlineQueryResultArticle`, `InputTextMessageContent`, and `InlineQueryResultCachedSticker`;
- call `answer_inline_query(...)`;
- preserve the existing logging and error behaviour.

The application layer will own the inline-query semantics:

- effective user/public-pack fallback;
- empty-query default tag selection;
- help-content retrieval;
- sticker lookup;
- shuffle/cache behaviour;
- pagination;
- persistence after cache-affecting operations;
- chosen-result cache clearing.

Chosen boundary: introduce a `HelpContentProvider` application port now, so empty inline queries can be resolved by the application layer without importing Telegram or reading files directly from the use case.

## Goals

- Keep Telegram imports out of `bot/application/`.
- Preserve all current user-visible inline-query behaviour.
- Preserve YAML persistence format and persistence timing.
- Preserve current public/private pack semantics.
- Move inline-query decision logic out of `InlineHandler`.
- Make inline-query behaviour testable without Telegram objects.

## Non-Goals

- Do not refactor unrelated shared handler utilities.
- Do not change command names, replies, help wording, parse modes, or cache timing.
- Do not introduce new runtime dependencies.
- Do not redesign sticker storage or YAML persistence.
- Do not remove legacy quirks unless explicitly covered by a later compatibility-breaking step.

## Key Changes

### 1. Add A Help Content Port

Add an application port under `bot/application/ports/`:

```python
class HelpContentProvider(Protocol):
    def get_help_text(self) -> str:
        """Return the plain help text shown in the default inline help article."""
```

Add a filesystem-backed adapter under `bot/infrastructure/help/`, for example:

```python
@dataclass(frozen=True)
class FileHelpContentProvider:
    path: Path

    def get_help_text(self) -> str:
        return self.path.read_text(encoding="utf-8")
```

Wire it with the existing `HELP_PATH`.

Telegram parse mode, article title, article id, and `InputTextMessageContent` construction must stay in the handler.

### 2. Add Inline Query Use Cases

Add two use cases under `bot/application/use_cases/`.

#### `ResolveInlineQuery`

Responsibilities:

- resolve the effective pack using the same public/private semantics as the current handler;
- fall back to `SF_PUBLIC` when the requesting user is missing;
- resolve query tags;
- for empty queries at `offset == 0`, include default-help metadata and help text;
- preserve current default tag behaviour:
  - private-mode users use their own `random_tag()`;
  - public-mode or missing users use the public pack’s `random_tag()`;
  - keep the current one-item-list behaviour returned by `random_tag()`;
- retrieve sticker ids with the existing shuffle/cache behaviour;
- paginate with the legacy `49` limit;
- compute `next_offset`;
- save the effective user/pack after lookup when current behaviour mutates cache state.

#### `ClearInlineCache`

Responsibilities:

- resolve the effective user/pack using the same fallback semantics;
- clear cached stickers for the effective pack;
- save the affected user/pack through the repository;
- return an explicit cache-cleared result.

### 3. Reuse The Existing Effective-Pack Abstraction

If Step 3 introduced a domain service for resolving and mutating effective sticker packs, reuse it here.

The inline use cases should not duplicate logic for:

- private/public mode checks;
- `SF_PUBLIC` fallback;
- effective pack lookup;
- saving the mutated effective pack.

A good target shape is:

```python
@dataclass(frozen=True)
class ResolveInlineQuery:
    users: UserRepository
    packs: StickerPackService
    help_content: HelpContentProvider

    def execute(self, request: InlineQueryRequest) -> ResolvedInlineQuery:
        ...
```

The exact names can differ, but the dependency direction should remain:

```text
handler -> application use case -> domain service/repository port
```

### 4. Refine Application DTOs

Reuse existing DTOs where possible, but avoid naming collisions with Telegram classes.

Prefer application-specific names such as:

```python
@dataclass(frozen=True)
class InlineQueryRequest:
    user_id: int | None
    query_text: str
    offset: int
    limit: int = 49
```

```python
@dataclass(frozen=True)
class ClearInlineCacheCommand:
    user_id: int | None
    query_text: str = ""
```

```python
@dataclass(frozen=True)
class ResolvedInlineQuery:
    sticker_ids: list[str]
    default_tags: list[str]
    help_text: str | None
    show_default_help: bool
    next_offset: int
    cache_cleared: bool = False
```

```python
@dataclass(frozen=True)
class InlineCacheCleared:
    cache_cleared: bool = True
```

Avoid naming the application DTO `InlineQueryResult`, because `telegram.InlineQueryResult*` already exists and the overlap can make imports and tests harder to read.

Do not put these in application DTOs:

- Telegram result objects;
- Telegram parse modes;
- Telegram article ids;
- UUID generation;
- reply markup;
- handler log messages;
- `answer_inline_query(...)` arguments.

### 5. Keep Telegram-Specific Construction In `InlineHandler`

`InlineHandler` should keep responsibility for:

- reading `update.inline_query`;
- reading `update.effective_user`;
- reading `update.chosen_inline_result`;
- preserving the current invalid-offset exception/logging behaviour;
- building `InlineQueryRequest`;
- calling `ResolveInlineQuery`;
- converting `ResolvedInlineQuery` into Telegram inline results;
- generating Telegram-specific result ids;
- building the default help article with Markdown parse mode;
- building cached sticker results;
- calling:

```python
context.bot.answer_inline_query(
    inline_query.id,
    results,
    cache_time=1,
    is_personal=True,
    next_offset=str(result.next_offset),
)
```

- building `ClearInlineCacheCommand` from chosen-result updates;
- calling `ClearInlineCache`;
- preserving the current chosen-result log message.

## Compatibility Rules

### Effective Pack Resolution

Preserve current fallback behaviour:

- use the requesting user when present;
- otherwise use `SF_PUBLIC`;
- public-mode users resolve against the public pack;
- private-mode users resolve against their own pack.

### Empty Inline Query Behaviour

Preserve current empty-query behaviour:

- when `query_text == ""` and `offset == 0`, include one default help article before sticker results;
- the help article content must remain byte-for-byte equivalent after Markdown rendering inputs are considered;
- non-empty queries must not include the default help article;
- empty queries with `offset > 0` must not repeat the default help article unless current behaviour does.

### Default Tags

Preserve current default tag behaviour:

- private-mode users use their own `random_tag()`;
- public-mode or missing users use the public pack’s `random_tag()`;
- keep the existing one-item-list quirk from `random_tag()`.

### Pagination

Preserve legacy pagination:

```python
limit = 49
upper_bound = min(len(sticker_list), offset + 49)
next_offset = offset + 49
```

Do not “fix” `next_offset` to stop at the list length in this step unless current behaviour already does that.

### Cache Behaviour

Preserve existing cache mutation semantics:

- sticker resolution may mutate cached sticker order/state;
- chosen-result handling clears cached stickers;
- any mutated effective user/pack is saved through the repository;
- persistence still uses the current YAML format.

### Application Boundary

No imports from `telegram` are allowed under:

```text
bot/application/
```

The application layer must remain testable with plain Python objects.

## TDD Plan

### ~~Cycle 1: Characterize Current Handler Behaviour~~

Implemented in `tests/handlers/test_inline_handler.py`.

Regression tests now cover the current inline behaviour:

- empty inline query at offset `0` includes the default help article;
- non-empty inline query does not include the help article;
- sticker ids are converted into cached sticker inline results;
- `answer_inline_query(...)` is called with:
  - `cache_time=1`;
  - `is_personal=True`;
  - `next_offset` stringified;
- chosen-result handling clears cache and preserves current logging;
- invalid offset preserves current exception/logging behaviour.

Compatibility notes from this cycle:

- sticker result order is intentionally treated as unspecified because current resolution materializes sets;
- existing public-mode users currently return the union of their own matching stickers and public-pack matches;
- pagination is locked by count and legacy `next_offset = offset + 49`, not by a sorted sticker order.

### Cycle 2: Add `HelpContentProvider`

Add tests for the filesystem adapter:

- reads the configured file with UTF-8;
- returns the file content unchanged.

Keep this adapter thin. The use case should depend on the port, not on `Path` or `HELP_PATH`.

### Cycle 3: Add `ResolveInlineQuery`

Add application tests using fake repositories and fake help providers.

BDD examples:

- resolves missing user through public pack;
- resolves public-mode user through public pack;
- resolves private-mode user through private pack;
- empty query at offset `0` returns:
  - `show_default_help=True`;
  - `help_text`;
  - default tags;
- non-empty query returns:
  - `show_default_help=False`;
  - `help_text=None`;
- paginates sticker ids from `offset` through `offset + 49`;
- returns `next_offset == offset + 49`;
- preserves sticker count/set when shuffle is enabled, while allowing randomized order;
- saves the effective pack when sticker resolution mutates cache state.

Use data-driven tests for repeated public/private/missing-user resolution cases.

### Cycle 4: Add `ClearInlineCache`

Add application tests using fake repositories.

BDD examples:

- clears an existing private user cache and saves that user;
- clears public pack cache for missing user;
- clears public pack cache for public-mode user;
- returns `InlineCacheCleared(cache_cleared=True)`;
- does not import or construct Telegram objects.

### Cycle 5: Rewire `InlineHandler`

Inject use cases through `InlineHandler.__init__`.

Default production wiring may construct:

```python
repository = StickfixUserRepository(user_db)
help_provider = FileHelpContentProvider(HELP_PATH)
resolve_inline_query = ResolveInlineQuery(repository, pack_service, help_provider)
clear_inline_cache = ClearInlineCache(repository, pack_service)
```

Prefer accepting use cases as optional constructor arguments so tests can inject fakes without building the full infrastructure stack.

Example shape:

```python
class InlineHandler:
    def __init__(
        self,
        user_db: StickfixDB,
        resolve_inline_query: ResolveInlineQuery | None = None,
        clear_inline_cache: ClearInlineCache | None = None,
    ) -> None:
        ...
```

Handler regression tests should verify that it:

- builds `InlineQueryRequest` from Telegram inline query data;
- passes `user_id=None` when no effective user exists;
- preserves offset parsing behaviour;
- converts default-help results into the same help article shape;
- converts sticker ids into `InlineQueryResultCachedSticker`;
- calls `answer_inline_query(...)` with the same arguments as before;
- builds `ClearInlineCacheCommand` for chosen-result updates;
- preserves chosen-result logging/error behaviour.

## Test Plan

Run focused tests first:

```bash
uv run pytest tests/application/test_application_seam.py
uv run pytest tests/application/use_cases
uv run pytest tests/handlers
```

Then run the full suite:

```bash
uv run pytest
```

Recommended additional checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Acceptance Criteria

- `InlineHandler` no longer owns inline lookup, fallback, pagination, default-tag, or cache-clearing business logic.
- `bot/application/` has no Telegram imports.
- Empty inline query behaviour is unchanged.
- Pagination and `next_offset` behaviour are unchanged.
- Public/private pack resolution is unchanged.
- Cache clearing and save timing are unchanged.
- YAML output format is unchanged.
- Handler tests prove Telegram response construction remains compatible.
- Application tests prove inline behaviour without Telegram objects.
- Full test suite passes.

## Assumptions

- `HelpContentProvider` returns plain help text only.
- Markdown parse mode remains a Telegram-handler concern.
- Help article title/id construction remains a Telegram-handler concern.
- `query_text` on `ClearInlineCacheCommand` is retained only if current logging or cache-clearing behaviour needs it.
- Step 4 does not refactor unrelated handler utilities; that remains Step 5.
