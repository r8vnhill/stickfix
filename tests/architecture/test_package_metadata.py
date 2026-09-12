"""Contracts for workspace metadata and published dependency surfaces.

These tests inspect TOML and built wheel metadata rather than implementation
details. They protect the root runtime package and the extracted domain package
from silently acquiring the wrong dependencies or importable modules.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

import pytest
import tomllib
from conftest import ROOT

DEV_DEPENDENCIES = {
  "hypothesis",
  "pre-commit",
  "pyhamcrest",
  "pytest",
  "pytest-bdd",
  "pytest-cov",
  "ruff",
}


def load_pyproject(path: Path) -> dict[str, object]:
  """Load project metadata without coupling tests to TOML formatting."""
  with path.open("rb") as metadata_file:
    return tomllib.load(metadata_file)


def dependency_name(requirement: str) -> str:
  """Return the normalized distribution name at the start of a requirement."""
  name = re.split(r"[<>=!~\[]", requirement, maxsplit=1)[0]
  return name.strip().lower().replace("_", "-")


def project_metadata() -> dict[str, object]:
  """Return the root project's parsed metadata."""
  return load_pyproject(ROOT / "pyproject.toml")


def domain_metadata() -> dict[str, object]:
  """Return the ``stickfix-domain`` workspace member's parsed metadata."""
  return load_pyproject(ROOT / "packages" / "stickfix-domain" / "pyproject.toml")


def named_dependencies(requirements: list[str]) -> set[str]:
  """Return normalized distribution names from a dependency list."""
  return {dependency_name(requirement) for requirement in requirements}


def test_root_project_workspace_contract() -> None:
  """The current root package reserves the future workspace member location."""
  metadata = project_metadata()
  project = metadata["project"]
  tool = metadata["tool"]

  assert project["name"] == "stickfix-bot"
  assert project["requires-python"] == ">=3.14,<4"
  assert metadata["build-system"]["build-backend"] == "setuptools.build_meta"
  assert tool["uv"]["workspace"]["members"] == ["packages/*"]


def test_dependency_surfaces_keep_development_tools_out_of_runtime() -> None:
  """Development tools belong to the dev group, not published requirements."""
  metadata = project_metadata()
  project = metadata["project"]
  runtime_dependencies = named_dependencies(project["dependencies"])
  extras = project["optional-dependencies"]
  development_dependencies = named_dependencies(metadata["dependency-groups"]["dev"])

  assert not (DEV_DEPENDENCIES | {"uv"}) & runtime_dependencies
  assert development_dependencies == DEV_DEPENDENCIES
  assert set(extras) == {"db", "graph"}


def test_domain_package_has_no_runtime_dependencies() -> None:
  """``stickfix-domain`` is a workspace member with an empty dependency set."""
  root = project_metadata()["project"]
  domain = domain_metadata()["project"]

  assert domain["name"] == "stickfix-domain"
  assert domain["version"] == root["version"]
  assert domain["requires-python"] == root["requires-python"]
  assert domain_metadata()["build-system"]["build-backend"] == "setuptools.build_meta"
  assert domain["dependencies"] == []
  assert not named_dependencies(domain.get("dependencies", []))


def test_root_package_declares_stickfix_domain_as_a_workspace_dependency() -> None:
  """The root distribution depends on ``stickfix-domain`` via the workspace source."""
  metadata = project_metadata()
  project = metadata["project"]
  sources = metadata["tool"]["uv"]["sources"]

  assert "stickfix-domain" in named_dependencies(project["dependencies"])
  assert sources["stickfix-domain"] == {"workspace": True}


@pytest.mark.parametrize("extra", ["db", "graph"])
def test_published_optional_extras_are_preserved(extra: str) -> None:
  """The runtime optional extras remain part of the package contract."""
  metadata = project_metadata()

  assert metadata["project"]["optional-dependencies"][extra]


def _uv_executable() -> str:
  uv = shutil.which("uv")
  assert uv is not None, "uv must be installed for wheel contract tests"
  return uv


def _build_wheel(output_dir: Path, *build_args: str, pattern: str) -> Path:
  """Build one workspace wheel and return the artifact matching ``pattern``."""
  subprocess.run(  # noqa: S603 -- the executable is discovered locally for the contract.
    [_uv_executable(), "build", *build_args, "--out-dir", str(output_dir)],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  return next(output_dir.glob(pattern))


def _wheel_metadata(wheel: Path) -> tuple[list[str], object]:
  """Return archive members and parsed metadata for one wheel."""
  with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
    metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_name))
  return names, metadata


def test_built_wheel_excludes_development_dependency_surfaces(tmp_path: Path) -> None:
  """Consumers receive neither development requirements nor a dev extra."""
  wheel = _build_wheel(tmp_path, "--wheel", pattern="stickfix_bot-*.whl")
  _, wheel_metadata = _wheel_metadata(wheel)

  published_requirements = {
    dependency_name(requirement) for requirement in wheel_metadata.get_all("Requires-Dist", [])
  }
  assert not (DEV_DEPENDENCIES | {"uv"}) & published_requirements
  assert set(wheel_metadata.get_all("Provides-Extra", [])) == {"db", "graph"}


def test_built_domain_wheel_contains_only_the_stickfix_domain_package(tmp_path: Path) -> None:
  """The domain wheel packages ``stickfix_domain`` and no legacy ``bot`` package."""
  wheel = _build_wheel(
    tmp_path,
    "--package",
    "stickfix-domain",
    pattern="stickfix_domain-*.whl",
  )
  names, wheel_metadata = _wheel_metadata(wheel)

  assert any(name.startswith("stickfix_domain/") for name in names)
  assert not any(name.split("/", 1)[0] == "bot" for name in names)
  assert not wheel_metadata.get_all("Requires-Dist")


def _install_wheel_in_venv(venv_dir: Path, wheel: Path) -> Path:
  """Install ``wheel`` into an isolated environment and return its interpreter."""
  uv = _uv_executable()
  subprocess.run(  # noqa: S603 -- the executable is discovered locally for the contract.
    [uv, "venv", str(venv_dir)], check=True, capture_output=True, text=True
  )
  subprocess.run(  # noqa: S603 -- the wheel path is created by this test.
    [uv, "pip", "install", "--python", str(venv_dir), str(wheel)],
    check=True,
    capture_output=True,
    text=True,
  )
  bin_dir = "Scripts" if os.name == "nt" else "bin"
  python_name = "python.exe" if os.name == "nt" else "python"
  return venv_dir / bin_dir / python_name


def test_domain_wheel_imports_in_isolation(tmp_path: Path) -> None:
  """The built domain wheel imports without workspace source files available."""
  wheel = _build_wheel(
    tmp_path / "dist",
    "--package",
    "stickfix-domain",
    pattern="stickfix_domain-*.whl",
  )
  python = _install_wheel_in_venv(tmp_path / "venv", wheel)
  result = subprocess.run(  # noqa: S603 -- the interpreter is created by this test.
    [
      str(python),
      "-c",
      "from stickfix_domain import SF_PUBLIC, StickfixUser, Switch, UserId, UserModes",
    ],
    capture_output=True,
    text=True,
  )

  assert result.returncode == 0, result.stderr
