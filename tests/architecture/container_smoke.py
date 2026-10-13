"""Standalone runtime probe for the Stickfix container image (run by the ``container`` CI job).

Feed it to the image through its normal ``uv run`` path, with networking disabled::

  docker run --rm -i --network none -e UV_OFFLINE=1 IMAGE uv run python - < container_smoke.py

It proves that the bot's imports work offline without a token or database, and that the image holds
exactly the locked runtime selection. It never constructs ``Stickfix`` or starts polling.

Constraints for maintainers:

- Standard library only, and never copied into the image (``test_container_contract.py`` checks
  the imports). ``normalize`` therefore duplicates ``package_contract_support.normalize_name``
  on purpose.
- Expected versions and excluded distributions come from the image's own ``/app/uv.lock``, so the
  probe never restates the dependency policy.
- Every check runs and all failures are reported together; the exit status is nonzero on failure.
"""

from __future__ import annotations

import importlib
import importlib.metadata as metadata
import re
import sys
import tomllib
from pathlib import Path

APP = Path("/app")
REQUIRED_MODULES = (
  "telegram",
  "imghdr",
  "bot.stickfix",
  "bot.__main__",
  "stickfix_domain",
  "stickfix_application",
)
WORKSPACE = ("stickfix-bot", "stickfix-domain", "stickfix-application")
REPRESENTATIVE = ("python-telegram-bot", "sqlalchemy", "alembic", "psycopg", "tornado", "urllib3")

Packages = dict[str, dict[str, object]]


def normalize(name: str) -> str:
  """Normalize a distribution name following PEP 503."""
  return re.sub(r"[-_.]+", "-", name).lower()


def installed_versions() -> dict[str, str]:
  """Return installed distribution versions keyed by normalized name."""
  return {normalize(dist.metadata["Name"]): dist.version for dist in metadata.distributions()}


def locked_packages() -> Packages:
  """Return the image's uv.lock packages keyed by normalized name."""
  lock = tomllib.loads((APP / "uv.lock").read_text(encoding="utf-8"))
  return {normalize(package["name"]): package for package in lock["package"]}


def dependency_names(package: dict[str, object]) -> list[str]:
  """Return the normalized names of a locked package's normal dependencies."""
  return [normalize(edge["name"]) for edge in package.get("dependencies", ())]


def runtime_closure(packages: Packages) -> set[str]:
  """Return every package reachable from the root's normal (non-dev, non-extra) dependencies."""
  pending = dependency_names(packages["stickfix-bot"])
  reached: set[str] = set()
  while pending:
    name = pending.pop()
    if name not in reached and name in packages:
      reached.add(name)
      pending.extend(dependency_names(packages[name]))
  return reached


def excluded_distributions(packages: Packages) -> set[str]:
  """Return dev-group and optional-extra distributions that are not also runtime dependencies."""
  root = packages["stickfix-bot"]
  groups = (root.get("dev-dependencies", {}), root.get("optional-dependencies", {}))
  selected = {
    normalize(edge["name"]) for group in groups for edges in group.values() for edge in edges
  }
  return selected - runtime_closure(packages)


def interpreter_failures() -> list[str]:
  """Check the Python version and that the probe runs inside the project environment."""
  failures = []
  if sys.version_info[:2] != (3, 14):
    failures.append(f"unexpected Python {sys.version.split()[0]}")
  if Path(sys.prefix).resolve() != (APP / ".venv").resolve():
    failures.append(f"not running from the project environment: {sys.prefix}")
  return failures


def import_failures() -> list[str]:
  """Import every required module and check that ``imghdr`` is the image-local shim."""
  failures = []
  for name in REQUIRED_MODULES:
    try:
      importlib.import_module(name)
    except Exception as error:  # noqa: BLE001 -- report every failing import.
      failures.append(f"import {name} failed: {error!r}")
  shim = sys.modules.get("imghdr")
  if shim is not None and Path(shim.__file__).resolve() != (APP / "imghdr.py").resolve():
    failures.append(f"imghdr resolved from {shim.__file__}")
  return failures


def distribution_failures(installed: dict[str, str], packages: Packages) -> list[str]:
  """Compare installed versions with the lock and reject dev-only or optional-only installs."""
  failures = [
    f"{name}: installed {installed.get(name)}, locked {packages[name]['version']}"
    for name in (*WORKSPACE, *REPRESENTATIVE)
    if installed.get(name) != str(packages[name]["version"])
  ]
  unexpected = sorted(excluded_distributions(packages) & set(installed))
  if unexpected:
    failures.append(f"development or optional-only distributions installed: {unexpected}")
  return failures


def main() -> int:
  """Run every container runtime check and report all failures together."""
  installed = installed_versions()
  failures = [
    *interpreter_failures(),
    *import_failures(),
    *distribution_failures(installed, locked_packages()),
  ]
  if failures:
    print("container smoke test failed:", *failures, sep="\n  - ", file=sys.stderr)
    return 1
  print(f"container smoke test passed ({len(REQUIRED_MODULES)} imports, {len(installed)} dists)")
  return 0


if __name__ == "__main__":
  sys.exit(main())
