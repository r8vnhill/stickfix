"""Workspace metadata and published dependency contracts.

These checks keep the root, domain, and application distributions aligned with
the workspace graph and prevent development requirements from reaching users.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from package_contract_support import (
  DEV_DEPENDENCIES,
  application_metadata,
  build_wheel,
  dependency_name,
  domain_metadata,
  install_wheel_in_venv,
  install_wheels_in_venv,
  named_dependencies,
  project_metadata,
  run_application_import_probe,
  wheel_metadata,
)


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


def test_domain_package_has_no_runtime_dependencies() -> None:
  """The domain workspace member matches the root Python and version contract."""
  root = project_metadata()["project"]
  domain_metadata_file = domain_metadata()
  domain = domain_metadata_file["project"]

  assert domain["name"] == "stickfix-domain"
  assert domain["version"] == root["version"]
  assert domain["requires-python"] == root["requires-python"]
  assert domain_metadata_file["build-system"]["build-backend"] == "setuptools.build_meta"
  assert not domain["dependencies"]


def test_application_package_depends_only_on_stickfix_domain() -> None:
  """The application workspace member has only the domain as a runtime dependency."""
  root = project_metadata()["project"]
  application_file = application_metadata()
  application = application_file["project"]

  assert application["name"] == "stickfix-application"
  assert application["version"] == root["version"]
  assert application["requires-python"] == root["requires-python"]
  assert application_file["build-system"]["build-backend"] == "setuptools.build_meta"
  assert named_dependencies(application["dependencies"]) == {"stickfix-domain"}


@pytest.mark.parametrize("distribution", ["stickfix-domain", "stickfix-application"])
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


def test_domain_wheel_contains_only_the_domain_package(tmp_path: Path) -> None:
  """The domain wheel has its package and no legacy bot or runtime requirements."""
  wheel = build_wheel(
    tmp_path,
    "--package",
    "stickfix-domain",
    pattern="stickfix_domain-*.whl",
  )
  names, metadata = wheel_metadata(wheel)

  assert any(name.startswith("stickfix_domain/") for name in names)
  assert not any(name.split("/", 1)[0] == "bot" for name in names)
  assert not metadata.get_all("Requires-Dist")


def test_application_wheel_contains_only_the_application_package(tmp_path: Path) -> None:
  """The application wheel depends only on the domain and has no legacy bot."""
  wheel = build_wheel(
    tmp_path,
    "--package",
    "stickfix-application",
    pattern="stickfix_application-*.whl",
  )
  names, metadata = wheel_metadata(wheel)

  assert any(name.startswith("stickfix_application/") for name in names)
  assert not any(name.split("/", 1)[0] == "bot" for name in names)
  published = {dependency_name(req) for req in metadata.get_all("Requires-Dist", [])}
  assert published == {"stickfix-domain"}


def test_domain_wheel_imports_in_isolation(tmp_path: Path) -> None:
  """The built domain wheel imports without workspace source files available."""
  wheel = build_wheel(
    tmp_path / "dist",
    "--package",
    "stickfix-domain",
    pattern="stickfix_domain-*.whl",
  )
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


def build_isolated_application_interpreter(tmp_path: Path) -> Path:
  """Build and install domain and application wheels in a temporary environment."""
  dist_dir = tmp_path / "dist"
  wheels = [
    build_wheel(dist_dir, "--package", "stickfix-domain", pattern="stickfix_domain-*.whl"),
    build_wheel(
      dist_dir,
      "--package",
      "stickfix-application",
      pattern="stickfix_application-*.whl",
    ),
  ]
  return install_wheels_in_venv(tmp_path / "venv", wheels)
