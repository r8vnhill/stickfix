"""Executable dependency policy checks.

The typed table in ``dependency_policy`` explains why each dependency exists.
These tests keep it consistent with ``pyproject.toml`` declarations, ``uv.lock``
resolutions, production imports, and the compatibility evidence it cites.
"""

from __future__ import annotations

import ast
import importlib
import sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import NoReturn

import pytest
from dependency_policy import (
  DEV,
  EXTRA_GRAPH,
  OVERRIDE,
  POLICY,
  RUNTIME,
  WORKSPACE_GRAPH,
  DependencyClass,
  DependencyPolicy,
  ImportMode,
  extra_dependencies,
  names_in,
  policy_for,
)
from import_graph_support import PackageBoundary, import_edges, python_modules
from package_contract_support import (
  ROOT,
  Requirement,
  application_metadata,
  domain_metadata,
  exported_requirements,
  locked_package,
  locked_package_versions,
  locked_requirement,
  lockfile,
  named_dependencies,
  normalize_specifier,
  parse_requirement,
  project_metadata,
  release_tuple,
)

DOCS_START = "<!-- dependency-policy:start -->"
DOCS_END = "<!-- dependency-policy:end -->"
REMOVED_DEPENDENCIES = ("coloredlogs", "neo4j-driver")
OPTIONAL_INTEGRATIONS = frozenset({"neo4j", "neo4j-driver", "pgvector"})
EXTRA_SELECTIONS: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
  ((), frozenset()),
  (("graph",), frozenset({"neo4j"})),
  (("db",), frozenset({"pgvector"})),
  (("graph", "db"), frozenset({"neo4j", "pgvector"})),
)
LOCAL_TOP_LEVEL_MODULES = {"imghdr"}
PRODUCTION_ROOTS: dict[str, tuple[PackageBoundary, ...]] = {
  "stickfix-bot": (
    PackageBoundary(namespace="bot", source_root=ROOT),
    PackageBoundary(namespace="alembic", source_root=ROOT),
  ),
  "stickfix-domain": (
    PackageBoundary(
      namespace="stickfix_domain", source_root=ROOT / "packages" / "stickfix-domain" / "src"
    ),
  ),
  "stickfix-application": (
    PackageBoundary(
      namespace="stickfix_application",
      source_root=ROOT / "packages" / "stickfix-application" / "src",
    ),
  ),
}
OWN_NAMESPACES = {
  "stickfix-bot": {"bot"},
  "stickfix-domain": {"stickfix_domain"},
  "stickfix-application": {"stickfix_application"},
}


def fail(message: str) -> NoReturn:
  """Fail a dependency policy check with a clear message."""
  raise AssertionError(message)


# --- Declarations -----------------------------------------------------------------------------


def declared_surfaces() -> list[tuple[str, str]]:
  """Return every root declaration as (normalized name, surface), duplicates included."""
  metadata = project_metadata()
  project = metadata["project"]
  declared = [(name, RUNTIME) for name in map(_name, project["dependencies"])]
  for extra, requirements in project["optional-dependencies"].items():
    declared.extend((_name(requirement), f"extra:{extra}") for requirement in requirements)
  declared.extend((_name(requirement), DEV) for requirement in metadata["dependency-groups"][DEV])
  overrides = metadata["tool"]["uv"]["override-dependencies"]
  declared.extend((_name(requirement), OVERRIDE) for requirement in overrides)
  return declared


def _name(requirement: str) -> str:
  return parse_requirement(requirement).name


def test_every_declaration_has_exactly_one_policy_entry_on_its_surface() -> None:
  """Given the policy, every declared dependency has one entry on the correct surface."""
  declared = Counter(declared_surfaces())
  documented = Counter((entry.name, entry.surface) for entry in POLICY)

  assert not [key for key, count in declared.items() if count > 1], "duplicate declarations"
  assert not [key for key, count in documented.items() if count > 1], "duplicate policy entries"
  assert set(declared) - set(documented) == set(), "declarations missing a policy entry"
  assert set(documented) - set(declared) == set(), "policy entries without a declaration"


def test_policy_names_are_normalized_and_justified() -> None:
  """Every entry uses a PEP 503 name and explains why it is declared."""
  for entry in POLICY:
    assert entry.name == parse_requirement(entry.name).name, entry
    assert entry.justification.strip(), entry


@pytest.mark.parametrize("removed", REMOVED_DEPENDENCIES)
def test_removed_dependencies_are_not_declared_or_locked(removed: str) -> None:
  """Dependencies removed by maintainer decision stay out of declarations and the lock."""
  assert removed not in {name for name, _ in declared_surfaces()}
  assert locked_package_versions(removed) == []


def test_internal_entries_match_workspace_sources_and_graph() -> None:
  """Internal policy entries are exactly the workspace-sourced edges of the recorded graph."""
  metadata = project_metadata()
  internal = {entry.name for entry in POLICY if entry.dependency_class is DependencyClass.INTERNAL}
  sources = metadata["tool"]["uv"]["sources"]
  members = {
    "stickfix-bot": metadata["project"],
    "stickfix-domain": domain_metadata()["project"],
    "stickfix-application": application_metadata()["project"],
  }

  assert internal == set(WORKSPACE_GRAPH["stickfix-bot"])
  assert {name for name, source in sources.items() if source == {"workspace": True}} == internal
  for distribution, project in members.items():
    workspace_edges = named_dependencies(project["dependencies"]) & set(WORKSPACE_GRAPH)
    assert workspace_edges == WORKSPACE_GRAPH[distribution], distribution


# --- Import ownership -------------------------------------------------------------------------


def production_top_level_imports(distribution: str) -> dict[str, list[str]]:
  """Map third-party top-level imports in a distribution's sources to their locations."""
  ignored = sys.stdlib_module_names | OWN_NAMESPACES[distribution] | LOCAL_TOP_LEVEL_MODULES
  imports: dict[str, list[str]] = {}
  for boundary in PRODUCTION_ROOTS[distribution]:
    for path in python_modules(boundary):
      for edge in import_edges(path, boundary):
        top_level = edge.imported.partition(".")[0]
        if top_level not in ignored:
          location = f"{path.relative_to(ROOT).as_posix()}:{edge.line}"
          imports.setdefault(top_level, []).append(location)
  return imports


def distribution_dependencies(distribution: str) -> set[str]:
  """Return the direct runtime dependency names a distribution publishes."""
  if distribution == "stickfix-bot":
    return {entry.name for entry in POLICY if entry.surface == RUNTIME}
  metadata = {"stickfix-domain": domain_metadata, "stickfix-application": application_metadata}
  return named_dependencies(metadata[distribution]()["project"]["dependencies"])


def namespace_owners() -> dict[str, str]:
  """Map each import namespace named by the policy to its distribution."""
  return {namespace: entry.name for entry in POLICY for namespace in entry.imports}


@pytest.mark.parametrize("distribution", sorted(PRODUCTION_ROOTS))
def test_production_imports_are_declared_by_the_importing_distribution(distribution: str) -> None:
  """Given an external production import, its distribution declares the owning dependency."""
  owners = namespace_owners()
  declared = distribution_dependencies(distribution)
  nonconformances = [
    f"{location}: imports {namespace} owned by {owners.get(namespace, '<no policy entry>')}"
    for namespace, locations in production_top_level_imports(distribution).items()
    if owners.get(namespace) not in declared
    for location in locations
  ]

  assert not nonconformances, "\n".join(nonconformances)


@pytest.mark.parametrize(
  "entry",
  [entry for entry in POLICY if entry.import_mode is ImportMode.DIRECT],
  ids=lambda entry: entry.name,
)
def test_direct_dependencies_are_imported_by_production_code(entry: DependencyPolicy) -> None:
  """Given a direct dependency, its declared namespaces are used by production code."""
  imported = {
    namespace
    for distribution in PRODUCTION_ROOTS
    for namespace in production_top_level_imports(distribution)
  }

  assert entry.imports, f"{entry.name} is DIRECT but names no import namespace"
  assert set(entry.imports) <= imported, f"{entry.name} is not imported by production code"


@pytest.mark.parametrize(
  "entry",
  [entry for entry in POLICY if entry.import_mode is not ImportMode.DIRECT],
  ids=lambda entry: f"{entry.name}-{entry.surface}",
)
def test_indirect_dependencies_are_not_imported_directly(entry: DependencyPolicy) -> None:
  """Dynamic, compatibility, and tool dependencies stay out of production import statements."""
  for distribution in PRODUCTION_ROOTS:
    imported = production_top_level_imports(distribution)
    assert not set(entry.imports) & set(imported), (entry.name, distribution)


def test_removed_dependencies_are_not_imported_by_production_code() -> None:
  """Production sources do not import dependencies removed from the policy."""
  for distribution in PRODUCTION_ROOTS:
    assert not set(REMOVED_DEPENDENCIES) & set(production_top_level_imports(distribution))


# --- Compatibility evidence -------------------------------------------------------------------


def defined_tests() -> set[str]:
  """Return test function names defined in this module, read from its source."""
  tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
  return {
    node.name
    for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
  }


@pytest.mark.parametrize(
  "entry",
  [entry for entry in POLICY if entry.verified_by is not None]
  + [entry for entry in POLICY if entry.dependency_class is DependencyClass.COMPATIBILITY],
  ids=lambda entry: entry.name,
)
def test_compatibility_entries_cite_an_existing_verification_test(
  entry: DependencyPolicy,
) -> None:
  """Given a compatibility-sensitive entry, it cites a concrete test that exists."""
  assert entry.verified_by is not None, f"{entry.name} has no verification test"
  path, separator, test_name = entry.verified_by.partition("::")

  assert separator and (ROOT / path).is_file(), entry.verified_by
  assert path == Path(__file__).relative_to(ROOT).as_posix(), entry.verified_by
  assert test_name in defined_tests(), entry.verified_by


def declared_requirement(name: str, surface: str = RUNTIME) -> Requirement:
  """Return the single parsed root requirement for one dependency on one surface."""
  metadata = project_metadata()
  if surface == OVERRIDE:
    requirements = metadata["tool"]["uv"]["override-dependencies"]
  else:
    requirements = metadata["project"]["dependencies"]
  matches = [
    parse_requirement(requirement)
    for requirement in requirements
    if parse_requirement(requirement).name == name
  ]
  assert len(matches) == 1, (name, surface, matches)
  return matches[0]


def check_boundary(entry: DependencyPolicy, release: tuple[int, ...]) -> None:
  """Fail unless a release lies within an entry's approved version boundary."""
  boundary = entry.boundary
  assert boundary is not None, f"{entry.name} has no version boundary"
  if release < boundary.minimum:
    fail(f"{entry.name} {release} is below the approved minimum {boundary.minimum}")
  if release >= boundary.maximum_exclusive:
    fail(f"{entry.name} {release} is at or above {boundary.maximum_exclusive}")


BOUNDED_ENTRIES = [entry for entry in POLICY if entry.boundary is not None]


@pytest.mark.parametrize("entry", BOUNDED_ENTRIES, ids=lambda entry: entry.name)
def test_bounded_declarations_and_locks_match_their_approved_boundary(
  entry: DependencyPolicy,
) -> None:
  """Given a bounded policy entry, its declaration and its single locked release conform."""
  declared = declared_requirement(entry.name, entry.surface)
  locked = locked_package_versions(entry.name)

  assert declared.specifier == normalize_specifier(entry.boundary.specifier)
  assert len(locked) == 1, f"expected one locked {entry.name} release, got {locked}"
  check_boundary(entry, release_tuple(locked[0]))


def test_compatibility_boundaries_cover_the_ptb_baseline() -> None:
  """PTB and every compatibility pin carry an explicit version boundary."""
  bounded = {entry.name for entry in BOUNDED_ENTRIES}

  assert names_in(DependencyClass.COMPATIBILITY) | {"python-telegram-bot"} == bounded


def test_ptb_stays_on_the_approved_13_15_baseline() -> None:
  """PTB stays on its approved synchronous 13.x declaration and resolves to 13.15."""
  entry = policy_for("python-telegram-bot", RUNTIME)

  assert entry.boundary.specifier == ">=13.15,<14"
  assert locked_package_versions("python-telegram-bot") == ["13.15"]
  check_boundary(entry, release_tuple(version("python-telegram-bot")))


def test_psycopg_is_loaded_through_the_sqlalchemy_dialect() -> None:
  """The postgresql+psycopg URL dialect resolves its DBAPI to the declared psycopg driver."""
  from sqlalchemy.engine import make_url

  dialect = make_url("postgresql+psycopg://user@localhost/stickfix").get_dialect()

  assert dialect.import_dbapi().__name__ == "psycopg"
  assert declared_requirement("psycopg").extras == ("binary",)


def test_urllib3_stays_on_the_ptb_fallback_line() -> None:
  """urllib3 1.26.x stays resolved and keeps the contrib module PTB 13's fallback imports."""
  entry = policy_for("urllib3", RUNTIME)

  assert entry.boundary.specifier == ">=1.26,<1.27"
  check_boundary(entry, release_tuple(version("urllib3")))
  assert importlib.import_module("urllib3.contrib.appengine") is not None


def test_six_stays_within_its_retained_bound() -> None:
  """six stays within its retained bound and is still required through APScheduler."""
  entry = policy_for("six", RUNTIME)
  apscheduler = {dependency["name"] for dependency in locked_package("apscheduler")["dependencies"]}
  ptb = {dependency["name"] for dependency in locked_package("python-telegram-bot")["dependencies"]}

  assert entry.boundary.specifier == ">=1.17,<1.18"
  check_boundary(entry, release_tuple(version("six")))
  assert "six" in apscheduler
  assert "apscheduler" in ptb


def test_resolved_tornado_version_is_patched_and_bounded() -> None:
  """The installed Tornado must stay within the patched 6.x line."""
  check_boundary(policy_for("tornado", OVERRIDE), release_tuple(version("tornado")))


def test_lockfile_contains_exactly_one_patched_tornado_release() -> None:
  """The committed uv lockfile must not regress to vulnerable Tornado."""
  entry = policy_for("tornado", OVERRIDE)
  tornado_versions = locked_package_versions("tornado")

  if len(tornado_versions) != 1:
    fail(f"Expected exactly one locked Tornado release, got {tornado_versions}")
  check_boundary(entry, release_tuple(tornado_versions[0]))
  assert entry.boundary.specifier == ">=6.5.5,<7"
  assert (entry.boundary.minimum, entry.boundary.maximum_exclusive) == ((6, 5, 5), (7, 0, 0))


def test_tornado_override_records_its_deployment_assumption_and_removal_condition() -> None:
  """The override is justified by polling-only startup, which its own tests still cover."""
  entry = policy_for("tornado", OVERRIDE)
  startup_tests = ROOT / "tests" / "test_startup_contract.py"
  startup_tree = ast.parse(startup_tests.read_text(encoding="utf-8"))
  startup_names = {node.name for node in startup_tree.body if isinstance(node, ast.FunctionDef)}

  assert "polling" in entry.justification
  assert entry.removal_condition is not None
  assert "PTB migration" in entry.removal_condition
  assert "test_start_polling_service_starts_polling_and_never_webhook" in startup_names


# --- Documentation ----------------------------------------------------------------------------


def documented_policy() -> list[tuple[str, str, str, str]]:
  """Parse the delimited dependency-policy table rows from CONTRIBUTING.md."""
  text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
  _, start, rest = text.partition(DOCS_START)
  section, end, _ = rest.partition(DOCS_END)
  assert start and end, "CONTRIBUTING.md has no delimited dependency-policy section"
  rows = []
  for line in section.splitlines():
    if not line.lstrip().startswith("|"):
      continue
    cells = [_plain(cell) for cell in line.strip().strip("|").split("|")]
    if len(cells) != 4 or cells[0] == "Dependency" or set(cells[0]) <= set("-: "):
      continue
    rows.append((cells[0], cells[1], cells[2], cells[3]))
  return rows


def _plain(cell: str) -> str:
  """Collapse whitespace and drop inline-code markers from a Markdown table cell."""
  return " ".join(cell.replace("`", "").split())


def test_contributing_documents_every_policy_entry_once() -> None:
  """Given the executable policy, the documented table lists each entry exactly once."""
  documented = Counter((name, surface) for name, _, surface, _ in documented_policy())

  assert [key for key, count in documented.items() if count > 1] == []
  assert set(documented) == {(entry.name, entry.surface) for entry in POLICY}


def test_contributing_policy_rows_agree_with_the_executable_policy() -> None:
  """Documented classifications, surfaces, and purposes match their policy entries."""
  for name, classification, surface, purpose in documented_policy():
    entry = policy_for(name, surface)
    assert classification == entry.dependency_class.value, name
    assert purpose == _plain(entry.justification), name


# --- Lockfile consistency ---------------------------------------------------------------------


def expected_requires_dist() -> set[Requirement]:
  """Return root runtime and extra requirements as uv records them in lock metadata."""
  metadata = project_metadata()
  project = metadata["project"]
  sources = metadata["tool"]["uv"]["sources"]
  expected = {
    parse_requirement(requirement)
    for requirement in project["dependencies"]
    if parse_requirement(requirement).name not in sources
  }
  for extra, requirements in project["optional-dependencies"].items():
    expected |= {
      parse_requirement(requirement, marker=f"extra == '{extra}'") for requirement in requirements
    }
  return expected


def test_locked_root_metadata_matches_declared_requirements() -> None:
  """Given pyproject.toml and uv.lock, the root's locked metadata mirrors its declarations."""
  metadata = project_metadata()
  locked = locked_package("stickfix-bot")
  requires_dist = locked["metadata"]["requires-dist"]
  registry = {locked_requirement(entry) for entry in requires_dist if "editable" not in entry}
  editable = {entry["name"]: entry["editable"] for entry in requires_dist if "editable" in entry}

  assert registry == expected_requires_dist()
  assert editable == {name: f"packages/{name}" for name in metadata["tool"]["uv"]["sources"]}
  assert sorted(locked["metadata"]["provides-extras"]) == sorted(
    metadata["project"]["optional-dependencies"]
  )


def test_locked_root_dev_group_matches_declared_requirements() -> None:
  """The locked development group mirrors the declared dependency group."""
  locked = locked_package("stickfix-bot")
  declared = {
    parse_requirement(requirement) for requirement in project_metadata()["dependency-groups"][DEV]
  }

  assert {locked_requirement(entry) for entry in locked["metadata"]["requires-dev"][DEV]} == (
    declared
  )
  assert {entry["name"] for entry in locked["dev-dependencies"][DEV]} == {
    requirement.name for requirement in declared
  }


def test_locked_root_dependency_edges_match_declarations() -> None:
  """Locked runtime and extra edges name exactly the declared distributions and extras."""
  project = project_metadata()["project"]
  locked = locked_package("stickfix-bot")
  runtime = {
    (requirement.name, requirement.extras)
    for requirement in map(parse_requirement, project["dependencies"])
  }

  assert {
    (entry["name"], tuple(entry.get("extra", ()))) for entry in locked["dependencies"]
  } == runtime
  for extra, requirements in project["optional-dependencies"].items():
    assert {entry["name"] for entry in locked["optional-dependencies"][extra]} == (
      named_dependencies(requirements)
    )


def test_locked_override_matches_the_declared_override() -> None:
  """The lock manifest records the declared Tornado override unchanged."""
  declared = project_metadata()["tool"]["uv"]["override-dependencies"]
  overrides = {locked_requirement(entry) for entry in lockfile()["manifest"]["overrides"]}

  assert overrides == {parse_requirement(requirement) for requirement in declared}
  assert policy_for("tornado", OVERRIDE).dependency_class is DependencyClass.COMPATIBILITY


# --- Optional extras --------------------------------------------------------------------------


def test_graph_extra_is_supplied_by_exactly_one_neo4j_distribution() -> None:
  """Given the graph extra, Neo4j 6.x is supplied by exactly one distribution."""
  declared = named_dependencies(project_metadata()["project"]["optional-dependencies"]["graph"])
  (locked,) = locked_package_versions("neo4j")

  assert declared == {"neo4j"}
  assert extra_dependencies("graph") == declared
  assert policy_for("neo4j", EXTRA_GRAPH).dependency_class is DependencyClass.OPTIONAL
  assert locked_package_versions("neo4j-driver") == []
  assert (6,) <= release_tuple(locked) < (7,)
  for distribution in PRODUCTION_ROOTS:
    assert "neo4j" not in production_top_level_imports(distribution), distribution


@pytest.mark.parametrize(
  ("extras", "required"),
  EXTRA_SELECTIONS,
  ids=["default", "graph", "db", "graph+db"],
)
def test_extra_selection_installs_only_its_integrations(
  extras: tuple[str, ...], required: frozenset[str]
) -> None:
  """Given an extra selection, the locked export contains exactly its optional integrations."""
  exported = exported_requirements(*extras)
  runtime = {
    entry.name for entry in POLICY if entry.surface == RUNTIME and entry.name not in WORKSPACE_GRAPH
  }

  assert runtime <= set(exported)
  assert set(exported) & OPTIONAL_INTEGRATIONS == required
  if "neo4j" in required:
    assert exported["neo4j"] == locked_package_versions("neo4j")[0]
