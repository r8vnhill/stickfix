"""Executable dependency policy for the Stickfix workspace.

This table is authoritative for *why* each dependency is declared and *where*
it belongs. ``pyproject.toml`` remains authoritative for version specifiers,
and ``uv.lock`` for resolved versions; the dependency-policy tests check that
the three sources agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

POLICY_TESTS = "tests/architecture/test_dependency_policy.py"
RUNTIME = "runtime"
DEV = "dev"
OVERRIDE = "override"
EXTRA_DB = "extra:db"
EXTRA_GRAPH = "extra:graph"


class DependencyClass(StrEnum):
  """Why a dependency is declared."""

  INTERNAL = "internal"
  RUNTIME = "runtime"
  COMPATIBILITY = "compatibility"
  DEVELOPMENT = "development"
  OPTIONAL = "optional"


class ImportMode(StrEnum):
  """How project code reaches a dependency, independent of its classification."""

  DIRECT = "direct"
  DYNAMIC = "dynamic"
  TRANSITIVE_COMPATIBILITY = "transitive_compatibility"
  NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class VersionBoundary:
  """An approved release range and the specifier that declares it."""

  minimum: tuple[int, ...]
  maximum_exclusive: tuple[int, ...]
  specifier: str


@dataclass(frozen=True, slots=True)
class DependencyPolicy:
  """One declared dependency, its purpose, and the evidence that keeps it honest."""

  name: str
  dependency_class: DependencyClass
  surface: str
  justification: str
  import_mode: ImportMode
  imports: tuple[str, ...] = ()
  verified_by: str | None = None
  boundary: VersionBoundary | None = None
  removal_condition: str | None = None


def _verified_by(test_name: str) -> str:
  """Reference a behavioral test in the dependency-policy suite."""
  return f"{POLICY_TESTS}::{test_name}"


# Direct workspace edges per distribution; the policy must not silently change them.
WORKSPACE_GRAPH: dict[str, frozenset[str]] = {
  "stickfix-bot": frozenset({"stickfix-domain", "stickfix-application"}),
  "stickfix-application": frozenset({"stickfix-domain"}),
  "stickfix-domain": frozenset(),
}

POLICY: tuple[DependencyPolicy, ...] = (
  DependencyPolicy(
    "stickfix-domain",
    DependencyClass.INTERNAL,
    RUNTIME,
    "Telegram-free user and sticker rules.",
    ImportMode.DIRECT,
    ("stickfix_domain",),
  ),
  DependencyPolicy(
    "stickfix-application",
    DependencyClass.INTERNAL,
    RUNTIME,
    "Transport-agnostic use cases, ports, and DTOs.",
    ImportMode.DIRECT,
    ("stickfix_application",),
  ),
  DependencyPolicy(
    "python-telegram-bot",
    DependencyClass.RUNTIME,
    RUNTIME,
    "PTB 13.15 synchronous Telegram framework.",
    ImportMode.DIRECT,
    ("telegram",),
    _verified_by("test_ptb_stays_on_the_approved_13_15_baseline"),
    VersionBoundary((13, 15), (14,), ">=13.15,<14"),
  ),
  DependencyPolicy(
    "pyyaml",
    DependencyClass.RUNTIME,
    RUNTIME,
    "Historical YAML import for one-shot PostgreSQL migration.",
    ImportMode.DIRECT,
    ("yaml",),
  ),
  DependencyPolicy(
    "sqlalchemy",
    DependencyClass.RUNTIME,
    RUNTIME,
    "PostgreSQL persistence models, sessions, and repositories.",
    ImportMode.DIRECT,
    ("sqlalchemy",),
  ),
  DependencyPolicy(
    "alembic",
    DependencyClass.RUNTIME,
    RUNTIME,
    "PostgreSQL schema migrations.",
    ImportMode.DIRECT,
    ("alembic",),
  ),
  DependencyPolicy(
    "psycopg",
    DependencyClass.RUNTIME,
    RUNTIME,
    "PostgreSQL driver loaded through SQLAlchemy's dialect.",
    ImportMode.DYNAMIC,
    ("psycopg",),
    _verified_by("test_psycopg_is_loaded_through_the_sqlalchemy_dialect"),
  ),
  DependencyPolicy(
    "urllib3",
    DependencyClass.COMPATIBILITY,
    RUNTIME,
    "PTB 13's Python 3.14 urllib3 fallback.",
    ImportMode.TRANSITIVE_COMPATIBILITY,
    ("urllib3",),
    _verified_by("test_urllib3_stays_on_the_ptb_fallback_line"),
    VersionBoundary((1, 26), (1, 27), ">=1.26,<1.27"),
  ),
  DependencyPolicy(
    "six",
    DependencyClass.COMPATIBILITY,
    RUNTIME,
    "Transitive PTB 13 APScheduler requirement.",
    ImportMode.TRANSITIVE_COMPATIBILITY,
    ("six",),
    _verified_by("test_six_stays_within_its_retained_bound"),
    VersionBoundary((1, 17), (1, 18), ">=1.17,<1.18"),
  ),
  DependencyPolicy(
    "tornado",
    DependencyClass.COMPATIBILITY,
    OVERRIDE,
    "Patched PTB 13.15 Tornado override for polling.",
    ImportMode.TRANSITIVE_COMPATIBILITY,
    ("tornado",),
    _verified_by("test_lockfile_contains_exactly_one_patched_tornado_release"),
    VersionBoundary((6, 5, 5), (7, 0, 0), ">=6.5.5,<7"),
    "Replace only during an approved PTB migration that demonstrates equivalent behavior and no "
    "dependency-security regression.",
  ),
  DependencyPolicy(
    "pgvector",
    DependencyClass.OPTIONAL,
    EXTRA_DB,
    "Optional database vector support.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "neo4j",
    DependencyClass.OPTIONAL,
    EXTRA_GRAPH,
    "Optional graph driver; currently unused.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "hypothesis",
    DependencyClass.DEVELOPMENT,
    DEV,
    "Property-based tests.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "pyhamcrest",
    DependencyClass.DEVELOPMENT,
    DEV,
    "Matcher-style test assertions.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "pytest",
    DependencyClass.DEVELOPMENT,
    DEV,
    "Test runner.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "pytest-bdd",
    DependencyClass.DEVELOPMENT,
    DEV,
    "Gherkin scenarios for BDD tests.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "pytest-cov",
    DependencyClass.DEVELOPMENT,
    DEV,
    "Coverage collection.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "ruff",
    DependencyClass.DEVELOPMENT,
    DEV,
    "Linting and formatting.",
    ImportMode.NOT_APPLICABLE,
  ),
)


def names_in(dependency_class: DependencyClass) -> frozenset[str]:
  """Return policy names with one classification."""
  return frozenset(entry.name for entry in POLICY if entry.dependency_class is dependency_class)


def dev_dependencies() -> frozenset[str]:
  """Return development dependency-group members."""
  return frozenset(entry.name for entry in POLICY if entry.surface == DEV)


def extra_dependencies(extra: str) -> frozenset[str]:
  """Return the dependencies published by one optional extra."""
  return frozenset(entry.name for entry in POLICY if entry.surface == f"extra:{extra}")


def policy_for(name: str, surface: str) -> DependencyPolicy:
  """Return the single policy entry for a dependency on one declaration surface."""
  matches = [entry for entry in POLICY if entry.name == name and entry.surface == surface]
  assert len(matches) == 1, f"expected one policy entry for {name} on {surface}, got {matches}"
  return matches[0]
