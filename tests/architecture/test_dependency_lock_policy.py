"""Check that committed lock metadata mirrors the root dependency declarations."""

from __future__ import annotations

from dependency_policy import DEV, OVERRIDE, DependencyClass, policy_for
from package_contract_support import (
  Requirement,
  locked_package,
  locked_requirement,
  lockfile,
  named_dependencies,
  parse_requirement,
  project_metadata,
)


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
  """Given pyproject.toml and uv.lock, root metadata mirrors its declarations."""
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
  """Locked runtime and extra edges name the declared distributions and extras."""
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
