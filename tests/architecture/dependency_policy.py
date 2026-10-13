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
class DependencyPolicy:
  """One declared dependency, its purpose, and the evidence that keeps it honest."""

  name: str
  dependency_class: DependencyClass
  surface: str
  justification: str
  import_mode: ImportMode
  imports: tuple[str, ...] = ()
  verified_by: str | None = None


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
    "Workspace member with Telegram-free user and sticker rules.",
    ImportMode.DIRECT,
    ("stickfix_domain",),
  ),
  DependencyPolicy(
    "stickfix-application",
    DependencyClass.INTERNAL,
    RUNTIME,
    "Workspace member with transport-agnostic use cases, ports, and DTOs.",
    ImportMode.DIRECT,
    ("stickfix_application",),
  ),
  DependencyPolicy(
    "python-telegram-bot",
    DependencyClass.RUNTIME,
    RUNTIME,
    "Approved synchronous Telegram framework baseline (PTB 13.15) used by handlers and startup.",
    ImportMode.DIRECT,
    ("telegram",),
    _verified_by("test_ptb_stays_on_the_approved_13_15_baseline"),
  ),
  DependencyPolicy(
    "pyyaml",
    DependencyClass.RUNTIME,
    RUNTIME,
    "Reads historical YAML data for the documented one-shot PostgreSQL migration.",
    ImportMode.DIRECT,
    ("yaml",),
  ),
  DependencyPolicy(
    "sqlalchemy",
    DependencyClass.RUNTIME,
    RUNTIME,
    "PostgreSQL runtime persistence models, sessions, and repositories.",
    ImportMode.DIRECT,
    ("sqlalchemy",),
  ),
  DependencyPolicy(
    "alembic",
    DependencyClass.RUNTIME,
    RUNTIME,
    "PostgreSQL schema migrations applied before the bot starts.",
    ImportMode.DIRECT,
    ("alembic",),
  ),
  DependencyPolicy(
    "psycopg",
    DependencyClass.RUNTIME,
    RUNTIME,
    "PostgreSQL driver loaded by SQLAlchemy through the postgresql+psycopg URL dialect.",
    ImportMode.DYNAMIC,
    ("psycopg",),
    _verified_by("test_psycopg_is_loaded_through_the_sqlalchemy_dialect"),
  ),
  DependencyPolicy(
    "urllib3",
    DependencyClass.COMPATIBILITY,
    RUNTIME,
    "PTB 13 falls back to upstream urllib3 1.26.x (with urllib3.contrib.appengine) when its "
    "vendored copy cannot load on Python 3.14.",
    ImportMode.TRANSITIVE_COMPATIBILITY,
    ("urllib3",),
    _verified_by("test_urllib3_stays_on_the_ptb_fallback_line"),
  ),
  DependencyPolicy(
    "six",
    DependencyClass.COMPATIBILITY,
    RUNTIME,
    "Retained legacy bound; also required transitively by PTB 13's APScheduler. Revisit during "
    "PTB modernization.",
    ImportMode.TRANSITIVE_COMPATIBILITY,
    ("six",),
    _verified_by("test_six_stays_within_its_retained_bound"),
  ),
  DependencyPolicy(
    "tornado",
    DependencyClass.COMPATIBILITY,
    OVERRIDE,
    "Overrides PTB 13.15's tornado==6.1 pin with patched 6.x (CVE-2026-31958); acceptable "
    "because Stickfix starts by polling only.",
    ImportMode.TRANSITIVE_COMPATIBILITY,
    ("tornado",),
    _verified_by("test_lockfile_contains_exactly_one_patched_tornado_release"),
  ),
  DependencyPolicy(
    "pgvector",
    DependencyClass.OPTIONAL,
    EXTRA_DB,
    "Published db extra for vector-search experiments; not required by Stickfix persistence.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "neo4j",
    DependencyClass.OPTIONAL,
    EXTRA_GRAPH,
    "Published graph extra supplying the supported Neo4j 6.x Python driver.",
    ImportMode.NOT_APPLICABLE,
  ),
  DependencyPolicy(
    "neo4j-driver",
    DependencyClass.OPTIONAL,
    EXTRA_GRAPH,
    "Legacy Neo4j 5.x distribution overlapping the neo4j namespace; pending removal in B.2.",
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
    "pre-commit",
    DependencyClass.DEVELOPMENT,
    DEV,
    "Local git hook runner.",
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
