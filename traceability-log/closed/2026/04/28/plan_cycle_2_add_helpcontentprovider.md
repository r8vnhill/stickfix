# [PLAN] Cycle 2 — Add `HelpContentProvider`

## Summary

Introduce a Telegram-free `HelpContentProvider` application port and a filesystem-backed `FileHelpContentProvider` infrastructure adapter.

This cycle prepares the seam needed by the future inline-query application use case. It does **not** change handler behaviour, help text content, Markdown rendering, inline-query results, or runtime wiring.

The goal is to make help-content retrieval injectable and testable while preserving the current behaviour of reading the existing `HELP.md` content as plain text.

---

## Design Decisions

* Add a narrow application port:

```python
class HelpContentProvider(Protocol):
    def get_help_text(self) -> str: ...
```

* Use `@runtime_checkable` only if the existing application ports already use that convention.
* Keep the port in `bot/application/ports/help_content.py`.
* Export it from `bot/application/ports/__init__.py`.
* Add a filesystem adapter in infrastructure, not application.
* The adapter reads text using UTF-8.
* The adapter returns file content unchanged.
* The adapter does **not** parse Markdown.
* The adapter does **not** know about Telegram parse modes.
* The adapter does **not** cache content in this cycle.
* Missing/unreadable files should raise the normal filesystem exception, unless the current runtime already has an explicit fallback behaviour.

I would avoid calling missing-file handling “graceful” unless there is a concrete fallback policy. For this cycle, explicit propagation is cleaner and easier to reason about.

---

## Files to Add or Modify

| File                                                           |      Action | Purpose                                |
| -------------------------------------------------------------- | ----------: | -------------------------------------- |
| `bot/application/ports/help_content.py`                        |         Add | Application port                       |
| `bot/application/ports/__init__.py`                            |      Modify | Public application-port export         |
| `bot/infrastructure/help/__init__.py`                          |         Add | Infrastructure package                 |
| `bot/infrastructure/help/file_help_content_provider.py`        |         Add | Filesystem adapter                     |
| `tests/infrastructure/help/test_file_help_content_provider.py` |         Add | Adapter contract tests                 |
| `tests/application/test_application_seam.py`                   | Re-run only | Verify application stays Telegram-free |

---

## TDD Cycle

### 1. Red: Adapter reads UTF-8 content unchanged

Add a test using `tmp_path`:

```python
def test_reads_help_text_from_utf8_file(tmp_path: Path) -> None:
    help_file = tmp_path / "HELP.md"
    help_file.write_text("# Help\n\nUse /add ✨\n", encoding="utf-8")

    provider = FileHelpContentProvider(help_file)

    assert provider.get_help_text() == "# Help\n\nUse /add ✨\n"
```

Expected failure: `FileHelpContentProvider` does not exist.

---

### 2. Green: Add the minimum adapter

Implement only enough code to pass:

```python
from pathlib import Path


class FileHelpContentProvider:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get_help_text(self) -> str:
        return self._path.read_text(encoding="utf-8")
```

Keep this intentionally boring.

---

### 3. Red: Adapter does not cache stale content

This is worth testing because the adapter contract should be explicit.

```python
def test_reads_current_file_content_on_each_call(tmp_path: Path) -> None:
    help_file = tmp_path / "HELP.md"
    help_file.write_text("first", encoding="utf-8")

    provider = FileHelpContentProvider(help_file)

    assert provider.get_help_text() == "first"

    help_file.write_text("second", encoding="utf-8")

    assert provider.get_help_text() == "second"
```

This documents that caching is not part of Cycle 2. If caching becomes desirable later, that should be a deliberate behaviour change.

---

### 4. Red: Missing files fail explicitly

Instead of “graceful error handling”, lock the real policy:

```python
def test_raises_when_help_file_is_missing(tmp_path: Path) -> None:
    provider = FileHelpContentProvider(tmp_path / "missing.md")

    with pytest.raises(FileNotFoundError):
        provider.get_help_text()
```

This prevents accidental silent fallbacks that could hide deployment/configuration mistakes.

---

### 5. Green: Add the application port

Create `bot/application/ports/help_content.py`:

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class HelpContentProvider(Protocol):
    def get_help_text(self) -> str:
        """Return the raw help text shown by Stickfix."""
```

Then export it from `bot/application/ports/__init__.py`.

---

### 6. Refactor: Align names and package boundaries

After tests pass:

* Check import order.
* Keep function bodies tiny.
* Avoid adding a base class.
* Avoid introducing a result DTO.
* Avoid adding a use case in this cycle.
* Avoid importing `Path` or filesystem concerns into `bot/application`.

---

## Verification

Run the narrow tests first:

```bash
uv run pytest tests/infrastructure/help/test_file_help_content_provider.py -v
```

Then verify the application seam:

```bash
uv run pytest tests/application/test_application_seam.py -v
```

Then run the normal project checks:

```bash
uv run pytest
uv run ruff check .
```

If the project uses formatting separately:

```bash
uv run ruff format --check .
```

---

## Acceptance Criteria

This cycle is complete when:

* `HelpContentProvider` exists in the application ports package.
* The application layer does not import Telegram or filesystem-specific infrastructure.
* `FileHelpContentProvider` reads UTF-8 text from a provided `Path`.
* File content is returned exactly as stored.
* Multiple reads reflect the current file content.
* Missing files raise `FileNotFoundError`.
* No handler behaviour changes.
* No inline-query behaviour changes.
* All targeted tests and seam checks pass.

---

## Non-Goals

Do **not** do these in Cycle 2:

* Do not modify `InlineHandler`.
* Do not modify `/help` command behaviour.
* Do not change `HELP.md`.
* Do not introduce Markdown parsing.
* Do not introduce Telegram parse-mode logic.
* Do not add caching.
* Do not add a `ResolveInlineQuery` use case yet.
* Do not wire the provider into runtime composition yet.
