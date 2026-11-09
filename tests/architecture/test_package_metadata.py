"""Workspace metadata and published dependency contracts.

These checks keep the root and every workspace member aligned with ``WORKSPACE_GRAPH`` and
prevent development requirements from reaching users. Member checks are parametrized over
``WORKSPACE_MEMBERS``; when a member gains or loses a third-party requirement, update
``MEMBER_THIRD_PARTY`` together with its ``pyproject.toml``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from dependency_policy import RUNTIME, WORKSPACE_GRAPH, WORKSPACE_MEMBERS, policy_for
from package_contract_support import (
  DEV_DEPENDENCIES,
  build_isolated_application_interpreter,
  build_package_wheel,
  build_wheel,
  dependency_name,
  import_namespace,
  install_wheel_in_venv,
  named_dependencies,
  parse_requirement,
  project_metadata,
  run_application_import_probe,
  wheel_metadata,
  workspace_member_metadata,
)

# Third-party runtime requirements each member publishes; internal edges come from the graph.
MEMBER_THIRD_PARTY: dict[str, frozenset[str]] = {
  "stickfix-domain": frozenset(),
  "stickfix-application": frozenset({"expression"}),
  "stickfix-telegram": frozenset({"python-telegram-bot"}),
}


def test_root_project_workspace_contract() -> None:
  """The root package declares the workspace layout used for package builds."""
  metadata = project_metadata()
  project = metadata["project"]
  tool = metadata["tool"]

  assert project["name"] == "stickfix-bot"
  assert project["requires-python"] == ">=3.14,<4"
  assert metadata["build-system"]["build-backend"] == "setuptools.build_meta"
  assert tool["uv"]["workspace"]["members"] == ["packages/*"]


def test_dependency_surfaces_keep_development_tools_out_of_runtime() -> None:
  """Development tools stay in the dev group, outside published requirements."""
  metadata = project_metadata()
  project = metadata["project"]
  runtime = named_dependencies(project["dependencies"])
  development = named_dependencies(metadata["dependency-groups"]["dev"])

  assert not (DEV_DEPENDENCIES | {"uv"}) & runtime
  assert development == DEV_DEPENDENCIES
  assert set(project["optional-dependencies"]) == {"db", "graph"}


def member_requirements(member: str) -> frozenset[str]:
  """Return every runtime requirement a member publishes: its graph edges and third parties."""
  return WORKSPACE_GRAPH[member] | MEMBER_THIRD_PARTY[member]


def test_every_member_records_its_third_party_requirements() -> None:
  """A new member cannot join the workspace without declaring its external requirements here."""
  assert set(MEMBER_THIRD_PARTY) == set(WORKSPACE_MEMBERS)


@pytest.mark.parametrize("member", WORKSPACE_MEMBERS)
def test_member_metadata_matches_the_root_identity_and_its_requirements(member: str) -> None:
  """A member shares the root version, Python range, and backend; it declares only its edges."""
  root = project_metadata()["project"]
  metadata = workspace_member_metadata(member)
  project = metadata["project"]

  assert project["name"] == member
  assert project["version"] == root["version"]
  assert project["requires-python"] == root["requires-python"]
  assert metadata["build-system"]["build-backend"] == "setuptools.build_meta"
  assert named_dependencies(project["dependencies"]) == member_requirements(member)


def test_telegram_package_declares_the_approved_ptb_baseline() -> None:
  """The adapter package declares PTB with exactly the root's approved 13.x boundary."""
  dependencies = workspace_member_metadata("stickfix-telegram")["project"]["dependencies"]
  declared = {requirement.name: requirement for requirement in map(parse_requirement, dependencies)}
  boundary = policy_for("python-telegram-bot", RUNTIME).boundary

  assert declared["python-telegram-bot"] == parse_requirement(
    f"python-telegram-bot{boundary.specifier}"
  )


@pytest.mark.parametrize("distribution", WORKSPACE_MEMBERS)
def test_root_internal_dependencies_use_workspace_sources(distribution: str) -> None:
  """Root runtime packages resolve internal distributions from the workspace."""
  metadata = project_metadata()
  project = metadata["project"]
  sources = metadata["tool"]["uv"]["sources"]

  assert distribution in named_dependencies(project["dependencies"])
  assert sources[distribution] == {"workspace": True}


@pytest.mark.parametrize("extra", ["db", "graph"])
def test_published_optional_extras_are_preserved(extra: str) -> None:
  """Both documented optional runtime extras remain available to consumers."""
  assert project_metadata()["project"]["optional-dependencies"][extra]


def test_built_root_wheel_excludes_development_dependency_surfaces(tmp_path: Path) -> None:
  """The root wheel publishes runtime requirements and its two declared extras only."""
  wheel = build_wheel(tmp_path, "--wheel", pattern="stickfix_bot-*.whl")
  _, metadata = wheel_metadata(wheel)

  published = {dependency_name(req) for req in metadata.get_all("Requires-Dist", [])}
  assert not (DEV_DEPENDENCIES | {"uv"}) & published
  assert set(metadata.get_all("Provides-Extra", [])) == {"db", "graph"}


@pytest.mark.parametrize("member", WORKSPACE_MEMBERS)
def test_member_wheel_contains_only_its_package(member: str, tmp_path: Path) -> None:
  """A member wheel ships only its own import root (no ``bot`` tree) and its requirements."""
  names, metadata = wheel_metadata(build_package_wheel(tmp_path, member))
  top_levels = {name.split("/", 1)[0] for name in names}
  packages = {name for name in top_levels if not name.endswith(".dist-info")}

  assert packages == {import_namespace(member)}
  published = {dependency_name(req) for req in metadata.get_all("Requires-Dist", [])}
  assert published == member_requirements(member)


def test_domain_wheel_imports_in_isolation(tmp_path: Path) -> None:
  """The built domain wheel imports without workspace source files available."""
  wheel = build_package_wheel(tmp_path / "dist", "stickfix-domain")
  python = install_wheel_in_venv(tmp_path / "venv", wheel)
  result = run_domain_import_probe(python)

  assert result.returncode == 0, result.stderr


def run_domain_import_probe(python: Path) -> subprocess.CompletedProcess[str]:
  """Import representative domain APIs through the isolated interpreter."""
  return subprocess.run(  # noqa: S603 -- the interpreter is created by the test.
    [
      str(python),
      "-c",
      "from stickfix_domain import SF_PUBLIC, StickfixUser, Switch, UserId, UserModes",
    ],
    capture_output=True,
    text=True,
  )


def test_domain_and_application_wheels_import_together_in_isolation(tmp_path: Path) -> None:
  """The two extracted wheels import without Telegram or persistence dependencies."""
  python = build_isolated_application_interpreter(tmp_path)
  result = run_application_import_probe(python, tmp_path)

  assert result.returncode == 0, result.stderr
  assert result.stdout.strip() == ""
