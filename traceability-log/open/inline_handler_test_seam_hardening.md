# [PLAN] Inline Handler Test-Seam Hardening

## Summary

Refactor the inline-handler test structure so the long-term contract is based on public handler registration and transport translation, not name-mangled private methods or duplicated application-layer business rules.

This is a **behavior-preserving** refactor. Keep the current Telegram wire behaviour stable:

* existing help article shape;
* Markdown parse mode;
* `cache_time=1`;
* `is_personal=True`;
* current offset parsing behaviour;
* current `next_offset` stringification;
* current `49` result limit;
* current application ownership of pagination, fallback resolution, and cache clearing.

Defer production behaviour changes such as deterministic pagination or using the full Telegram 50-result capacity.

---

# Phase 1: Lock the Handler’s Public Registration Seam

## Goal

Replace direct private-method invocation with tests that exercise the callbacks registered through Telegram handler registration.

## Scope

In scope:

* assert that `InlineHandler` registers one inline-query handler and one chosen-inline-result handler;
* retrieve registered callbacks from the fake dispatcher;
* invoke those callbacks instead of calling `handler._InlineHandler__inline_get`;
* preserve existing handler behaviour.

Out of scope:

* changing production behaviour;
* extracting a new adapter module;
* changing pagination semantics;
* changing the result limit from `49`.

## Cycle 1.1 — Register Inline Query and Chosen Result Handlers [DONE]

### Red

Add a failing test:

```python
def test_inline_handler_registers_inline_query_and_chosen_result_handlers() -> None:
    ...
```

BDD-style assertions:

* should register an inline-query handler;
* should register a chosen-inline-result handler;
* should preserve the current registration count and callback availability.

### Green

Expose enough information through `FakeDispatcher` to inspect registered handlers.

If the Telegram handler classes expose callback attributes, assert against those. Otherwise, add small test helpers that locate handlers by class.

### Refactor

Move handler lookup into helper functions:

```python
def inline_query_callback(dispatcher: FakeDispatcher) -> Callable[..., object]:
    ...

def chosen_result_callback(dispatcher: FakeDispatcher) -> Callable[..., object]:
    ...
```

### Acceptance Criteria

* Tests no longer need to know private method names.
* Registration behaviour is explicitly covered.
* Existing handler tests still pass after callback invocation is routed through registration.

### Status

Implemented in `tests/handlers/test_inline_handler.py` by adding public-registration coverage for the inline-query and chosen-inline-result handlers and helper functions that locate the registered callbacks.

---

## Cycle 1.2 — Migrate Existing Handler Tests to the Registration Seam

### Red

Change one existing direct-private-call test to use the registered callback. Start with the simplest:

```python
def test_inline_query_builds_request_with_user_id_when_effective_user_exists() -> None:
    ...
```

It should fail until the helper invocation path is completed.

### Green

Update `call_inline_get` and chosen-result helpers so they invoke registered callbacks.

Preferred shape:

```python
def call_inline_get(
    dispatcher: FakeDispatcher,
    bot: FakeBot,
    *,
    user_id: int | None = 123,
    query: str = "wave",
    offset: str = "0",
    inline_query_id: str = "inline-1",
) -> None:
    ...
```

### Refactor

Change `make_handler` so tests can keep both the dispatcher and handler where needed:

```python
@dataclass
class HandlerHarness:
    dispatcher: FakeDispatcher
    handler: InlineHandler
    bot: FakeBot
```

### Acceptance Criteria

* No handler test calls name-mangled methods directly.
* Helper names describe Telegram scenarios, not implementation methods.
* Behaviour remains identical.

---

# Phase 2: Tighten the Injection Contract

## Goal

Make injected use cases structurally typed so tests and production wiring share the same callability contract.

## Scope

In scope:

* introduce protocol-based contracts or callable aliases;
* update `InlineHandler.__init__` annotations;
* keep production defaults unchanged;
* keep fake use cases simple.

Out of scope:

* changing application DTOs;
* changing use-case implementations;
* introducing a dependency injection framework.

## Cycle 2.1 — Introduce Callable Protocols for Injected Use Cases

### Red

Add or update a static-facing test/typing expectation if the project has type checks. Otherwise, make this a small refactor with existing tests as safety.

Candidate protocols:

```python
from typing import Protocol


class InlineQueryResolver(Protocol):
    def __call__(self, request: InlineQueryRequest) -> InlineQueryResult:
        ...


class InlineCacheClearer(Protocol):
    def __call__(self, command: ClearInlineCacheCommand) -> AcknowledgementResult:
        ...
```

### Green

Use these protocols in `InlineHandler.__init__` instead of concrete `ResolveInlineQuery | None` and `ClearInlineCache | None`.

### Refactor

Move protocols to the narrowest sensible location:

* `bot/handlers/inline.py` if they are handler-local;
* or `bot/handlers/inline_contracts.py` if the handler file is already crowded.

Prefer the local option unless multiple modules need the protocols.

### Acceptance Criteria

* Fake use cases satisfy the same shape as production use cases.
* Handler construction remains unchanged for production callers.
* Tests do not need inheritance-based fakes.

---

# Phase 3: Separate Handler Tests by Responsibility

## Goal

Make the test suite easier to maintain by separating registration, request/command mapping, Telegram result rendering, and legacy characterization coverage.

## Scope

In scope:

* split or reorganize `tests/handlers/test_inline_handler.py`;
* remove duplicated application business-rule assertions from handler tests;
* keep only handler-specific assertions in the handler suite.

Out of scope:

* deleting application use-case tests;
* changing use-case ownership;
* changing storage behaviour.

## Cycle 3.1 — Separate Registration Tests

### Red

Create a focused file:

```text
tests/handlers/test_inline_handler_registration.py
```

Move registration-seam tests there.

BDD-style examples:

```python
def test_registers_inline_query_handler() -> None: ...
def test_registers_chosen_inline_result_handler() -> None: ...
```

### Green

Move only registration assertions and required fixtures.

### Refactor

Keep shared fake dispatcher or harness helpers in one location if reused.

Suggested location:

```text
tests/handlers/fakes.py
```

or

```text
tests/handlers/inline_harness.py
```

### Acceptance Criteria

* Registration tests are independent from result rendering.
* Failures in Telegram result construction do not obscure registration failures.

---

## Cycle 3.2 — Keep Request and Command Mapping Tests

### Red

Create or isolate tests for pure mapping behaviour:

```python
def test_inline_query_builds_request_with_user_id_when_effective_user_exists() -> None: ...
def test_inline_query_builds_request_with_none_user_id_when_effective_user_is_missing() -> None: ...
def test_inline_query_builds_request_with_query_text_offset_and_limit() -> None: ...
def test_chosen_result_builds_command_with_user_id_when_effective_user_exists() -> None: ...
def test_chosen_result_builds_command_with_query_text() -> None: ...
```

### Green

Keep fake use cases that record calls and return minimal valid results.

### Refactor

Use DDT where it reduces duplication:

```python
@pytest.mark.parametrize(
    ("effective_user", "expected_user_id"),
    [
        (FakeTelegramUser(666), "666"),
        (None, None),
    ],
)
def test_inline_query_maps_effective_user_to_request_user_id(...) -> None:
    ...
```

Use varied Iron Maiden-inspired fake values if new fake data is needed, for example `user_id=666`, query text `"aces high"`, or sticker id `"trooper-sticker"`.

### Acceptance Criteria

* Mapping tests do not assert fallback, pagination, or cache ownership.
* Those business rules remain in application use-case tests.
* Handler tests only prove Telegram update data is translated into application DTOs.

---

## Cycle 3.3 — Keep Telegram Result Rendering Tests

### Red

Isolate tests for converting `InlineQueryResult` DTOs into Telegram result objects:

```python
def test_inline_query_builds_help_article_from_application_result() -> None: ...
def test_inline_query_maps_sticker_ids_to_cached_sticker_results() -> None: ...
def test_inline_query_answers_with_cache_time_personal_flag_and_next_offset() -> None: ...
```

### Green

Return controlled DTOs from fake resolvers.

Example controlled result:

```python
InlineQueryResult(
    sticker_ids=("trooper-sticker", "aces-high-sticker"),
    default_tags=("trooper",),
    show_default_help=False,
    help_text=None,
    next_offset=49,
)
```

### Refactor

Extract result assertions:

```python
def assert_cached_stickers(results: Sequence[object], expected_ids: tuple[str, ...]) -> None:
    ...
```

### Acceptance Criteria

* Rendering tests do not construct real domain users or repositories.
* Rendering tests assert Telegram object types and relevant fields.
* Application results remain the source of truth for what should be rendered.

---

# Phase 4: Clean Up Test Fixtures and Fakes

## Goal

Reduce test noise and make test failures easier to understand.

## Scope

In scope:

* introduce pytest fixtures for common setup;
* replace raw dictionary call recording in `FakeBot`;
* keep fakes minimal and typed.

Out of scope:

* replacing all fakes with mocks;
* adding new test dependencies.

## Cycle 4.1 — Add Fixtures for Common Setup

### Red

Refactor one test to use fixtures and let it fail until fixtures exist.

Suggested fixtures:

```python
@pytest.fixture
def store() -> FakeUserStore:
    ...


@pytest.fixture
def bot() -> FakeBot:
    ...


@pytest.fixture
def public_pack(store: FakeUserStore) -> StickfixUser:
    ...
```

### Green

Introduce fixtures and update one cluster of tests.

### Refactor

Apply fixtures across the file only after the first migrated cluster is green.

### Acceptance Criteria

* Repeated `store = FakeUserStore()`, `make_public_pack(store)`, and `bot = FakeBot()` setup is reduced.
* Test bodies focus on scenario-specific data.

---

## Cycle 4.2 — Replace `FakeBot` Dictionary Calls with a Typed Call Object

### Red

Update one assertion to use a typed answer call:

```python
answer = bot.single_inline_answer
assert_that(answer.inline_query_id, equal_to("inline-1"))
```

### Green

Introduce:

```python
@dataclass(frozen=True)
class AnswerInlineQueryCall:
    inline_query_id: str
    results: tuple[object, ...]
    cache_time: int
    is_personal: bool
    next_offset: str
```

Update `FakeBot.answer_inline_query` to store typed calls.

### Refactor

Replace helpers that index into `answer_inline_query_calls[0]["args"]`.

### Acceptance Criteria

* Tests no longer depend on positional dictionary internals.
* Assertion failures show meaningful field names.
* Fake bot remains small and framework-independent.

---

# Phase 5: Add Focused Edge-Case Coverage

## Goal

Lock the handler-specific edge cases that are easy to break during adapter refactoring.

## Scope

In scope:

* offset parsing matrix;
* no-answer-on-invalid-offset behaviour;
* optional missing-user mapping if reachable through public seam.

Out of scope:

* changing invalid offset behaviour;
* introducing clamping;
* changing empty-offset behaviour unless it already exists.

## Cycle 5.1 — Add DDT for Supported Offset Inputs

### Red

Add a parameterized test for currently supported valid offsets.

Example:

```python
@pytest.mark.parametrize(
    ("raw_offset", "expected_offset"),
    [
        ("0", 0),
        ("49", 49),
        ("98", 98),
    ],
)
def test_inline_query_maps_valid_offset(raw_offset: str, expected_offset: int) -> None:
    ...
```

Only include `""` if the current handler already accepts it.

### Green

Use the fake resolver to record the `InlineQueryRequest`.

### Refactor

Share the mapping assertion helper with existing request-building tests.

### Acceptance Criteria

* Valid offset mapping is explicit.
* Existing invalid-offset behaviour remains covered.
* No production behaviour change is introduced.

---

## Cycle 5.2 — Preserve Invalid Offset Failure Behaviour

### Red

Keep or move the existing invalid-offset test:

```python
def test_invalid_inline_query_offset_raises_value_error_and_does_not_answer_or_write() -> None:
    ...
```

### Green

Ensure it still passes through the public registration callback.

### Refactor

Make the expected behaviour explicit in the test name:

```python
def test_invalid_inline_query_offset_raises_before_answering() -> None:
    ...
```

### Acceptance Criteria

* Invalid offset still raises `ValueError`.
* Bot is not called.
* Store is not written.
* The test no longer calls private methods.

---

# Deferred Items / Non-Goals

## Defer deterministic pagination

Do not sort sticker IDs or assert exact page boundaries in this refactor. The application layer currently owns pagination behaviour, and changing set-materialized ordering could alter observable result order.

Track as a later behaviour-change proposal:

```text
Make inline sticker pagination deterministic by sorting sticker IDs before slicing.
```

## Defer Telegram 50-result capacity change

Do not replace `49` with dynamic capacity in this refactor.

Track as a later behaviour-change proposal:

```text
Use Telegram result capacity dynamically: 50 results without help article, 49 with help article.
```

## Defer a new adapter module unless the handler remains crowded

The smallest safe refactor is to keep helper functions near `InlineHandler`.

Extract a dedicated module only if the handler still mixes too many responsibilities after test cleanup:

```text
bot/handlers/inline_adapter.py
bot/handlers/inline_presenter.py
```

## Do not add Hypothesis yet

PBT is more valuable for pure application-layer invariants than for Telegram handler mapping. Use DDT for this cycle.

Possible future PBT targets:

* pagination invariants;
* cache clearing idempotence;
* fallback resolution;
* offset parser invariants, if extracted into a pure function.

---

# Suggested Execution Order

1. Add registration-seam tests.
2. Migrate existing private-method tests to registered callback invocation.
3. Introduce callable protocols for injected use cases.
4. Split handler tests by responsibility.
5. Clean up fixtures and fake bot call recording.
6. Add focused offset DDT.
7. Run application use-case tests.
8. Run handler tests.
9. Run application seam tests to confirm Telegram imports did not leak into `bot.application`.

---

# Final Acceptance Criteria

The refactor is complete when:

* no handler test calls `handler._InlineHandler__...`;
* handler registration is explicitly tested;
* handler tests only cover Telegram adapter responsibilities;
* application tests remain the canonical source for pagination, fallback, and cache clearing behaviour;
* injected fake use cases satisfy protocol/callable contracts;
* fake bot assertions are typed and readable;
* current wire behaviour is unchanged;
* no new dependency is introduced;
* the following suites pass:

```bash
pytest tests/application/use_cases/test_resolve_inline_query.py
pytest tests/application/use_cases/test_clear_inline_cache.py
pytest tests/handlers/
pytest tests/application/test_application_seam.py
```
