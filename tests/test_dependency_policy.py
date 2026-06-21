"""Executable dependency policy checks."""

from __future__ import annotations

import re
from importlib.metadata import version
from pathlib import Path
from typing import NoReturn

PATCHED_TORNADO_MINIMUM = (6, 5, 5)
NEXT_TORNADO_MAJOR = (7, 0, 0)


def fail(message: str) -> NoReturn:
    """Fail a dependency policy check with a clear message."""
    raise AssertionError(message)


def normalized_version(package_name: str) -> tuple[int, ...]:
    """Return the numeric release components for an installed package."""
    release = re.match(r"^\d+(?:\.\d+)*", version(package_name))
    if release is None:
        fail(f"{package_name} has an unparsable version")
    return parse_release(release.group(0))


def locked_versions(package_name: str) -> list[tuple[int, ...]]:
    """Return numeric versions for a package locked in uv.lock."""
    lockfile = Path(__file__).parents[1] / "uv.lock"
    package_blocks = lockfile.read_text(encoding="utf-8").split("[[package]]")
    versions: list[tuple[int, ...]] = []
    for block in package_blocks:
        if re.search(rf'(?m)^name = "{re.escape(package_name)}"$', block):
            version_match = re.search(r'(?m)^version = "([^"]+)"$', block)
            if version_match is None:
                fail(f"{package_name} has no locked version")
            versions.append(parse_release(version_match.group(1)))
    return versions


def parse_release(release: str) -> tuple[int, ...]:
    """Parse a plain dotted numeric release string."""
    return tuple(int(part) for part in release.split("."))


def check_patched_tornado_boundary(tornado_version: tuple[int, ...]) -> None:
    """Check that a Tornado version is patched and still on the 6.x line."""
    if tornado_version < PATCHED_TORNADO_MINIMUM:
        fail(f"Tornado {tornado_version} is below the patched minimum")
    if tornado_version >= NEXT_TORNADO_MAJOR:
        fail(f"Tornado {tornado_version} is outside the supported 6.x line")


def test_resolved_tornado_version_is_patched_and_bounded() -> None:
    """Tornado must stay within the patched 6.x line."""
    check_patched_tornado_boundary(normalized_version("tornado"))


def test_lockfile_contains_exactly_one_patched_tornado_release() -> None:
    """The committed uv lockfile must not regress to vulnerable Tornado."""
    tornado_versions = locked_versions("tornado")

    if len(tornado_versions) != 1:
        fail(f"Expected exactly one locked Tornado release, got {tornado_versions}")
    check_patched_tornado_boundary(tornado_versions[0])
