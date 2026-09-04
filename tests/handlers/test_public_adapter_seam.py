"""Guard against handler tests reaching into name-mangled private callbacks.

Handler tests should exercise the callbacks registered with the Telegram dispatcher (the
public adapter seam), not the name-mangled private methods the handler classes route those
callbacks to internally. Coupling tests to the mangled names would make routing changes
inside a handler break tests that never call `bot.handlers` directly, defeating the point of
testing through the seam. See tests/handlers/support.py for the shared helpers that make
testing through the seam convenient.
"""

from __future__ import annotations

from pathlib import Path

HANDLER_TEST_ROOT = Path(__file__).parent
PRIVATE_HANDLER_PREFIXES = (
    "_HelperHandler__",
    "_UserHandler__",
    "_StickerHandler__",
    "_InlineHandler__",
)


def test_handler_tests_do_not_access_name_mangled_callbacks() -> None:
    """Keep handler tests coupled to registered PTB callbacks, not implementations."""
    guard_path = Path(__file__).resolve()
    violations = [
        f"{path}:{line_number}: {prefix}"
        for path in HANDLER_TEST_ROOT.rglob("*.py")
        if path.resolve() != guard_path
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for prefix in PRIVATE_HANDLER_PREFIXES
        if prefix in line
    ]

    assert not violations, "private handler callback access found:\n" + "\n".join(violations)
