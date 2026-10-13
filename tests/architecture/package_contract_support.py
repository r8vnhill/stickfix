"""Shared helpers for workspace metadata and wheel contract tests.

The helpers keep build commands, archive inspection, and isolated interpreter
setup consistent while leaving each test module responsible for its own contract.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

import tomllib
from conftest import ROOT
from dependency_policy import DependencyClass, dev_dependencies, names_in

DEV_DEPENDENCIES = dev_dependencies()
OPTIONAL_DEPENDENCIES = names_in(DependencyClass.OPTIONAL)
REQUIREMENT_PATTERN = re.compile(
  r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*"
  r"(?:\[(?P<extras>[^\]]*)\])?\s*"
  r"(?P<specifier>[^;]*?)\s*"
  r"(?:;\s*(?P<marker>.+?))?\s*$"
)


@dataclass(frozen=True)
class Requirement:
  """A normalized requirement, comparable between pyproject and uv.lock forms."""

  name: str
  extras: tuple[str, ...] = ()
  specifier: str = ""
  marker: str | None = None


def load_pyproject(path: Path) -> dict[str, object]:
  """Load TOML metadata without coupling tests to file formatting."""
  with path.open("rb") as metadata_file:
    return tomllib.load(metadata_file)


def normalize_name(name: str) -> str:
  """Normalize a distribution name following PEP 503."""
  return re.sub(r"[-_.]+", "-", name.strip()).lower()


def dependency_name(requirement: str) -> str:
  """Normalize the distribution name at the start of a requirement."""
  return normalize_name(re.split(r"[<>=!~\[;\s]", requirement.strip(), maxsplit=1)[0])


def normalize_specifier(specifier: str) -> str:
  """Normalize a version specifier set by dropping whitespace and sorting its clauses."""
  clauses = (clause for clause in re.sub(r"\s+", "", specifier).split(",") if clause)
  return ",".join(sorted(clauses))


def parse_requirement(requirement: str, marker: str | None = None) -> Requirement:
  """Parse a PEP 508 requirement string without markers beyond an optional extra marker."""
  match = REQUIREMENT_PATTERN.match(requirement)
  assert match is not None, f"unparsable requirement: {requirement!r}"
  extras = match.group("extras") or ""
  return Requirement(
    name=normalize_name(match.group("name")),
    extras=tuple(sorted(normalize_name(extra) for extra in extras.split(",") if extra.strip())),
    specifier=normalize_specifier(match.group("specifier")),
    marker=match.group("marker") or marker,
  )


def locked_requirement(entry: dict[str, object]) -> Requirement:
  """Convert one uv.lock ``requires-dist``-style table to a normalized requirement."""
  return Requirement(
    name=normalize_name(str(entry["name"])),
    extras=tuple(sorted(normalize_name(extra) for extra in entry.get("extras", ()))),
    specifier=normalize_specifier(str(entry.get("specifier", ""))),
    marker=entry.get("marker"),
  )


def project_metadata() -> dict[str, object]:
  """Return parsed metadata for the root distribution."""
  return load_pyproject(ROOT / "pyproject.toml")


def workspace_member_metadata(distribution_directory: str) -> dict[str, object]:
  """Load a workspace member's metadata from its distribution directory."""
  path = ROOT / "packages" / distribution_directory / "pyproject.toml"
  return load_pyproject(path)


def domain_metadata() -> dict[str, object]:
  """Return parsed metadata for the domain workspace member."""
  return workspace_member_metadata("stickfix-domain")


def application_metadata() -> dict[str, object]:
  """Return parsed metadata for the application workspace member."""
  return workspace_member_metadata("stickfix-application")


def named_dependencies(requirements: list[str]) -> set[str]:
  """Normalize names from a list of dependency requirements."""
  return {dependency_name(requirement) for requirement in requirements}


def uv_executable() -> str:
  """Locate uv for artifact contract commands."""
  uv = shutil.which("uv")
  assert uv is not None, "uv must be installed for wheel contract tests"
  return uv


def run_uv(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
  """Run uv and include its output when a command fails."""
  result = subprocess.run(  # noqa: S603 -- the executable is discovered locally for tests.
    [uv_executable(), *args], cwd=cwd, capture_output=True, text=True
  )
  assert result.returncode == 0, f"uv {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
  return result


def build_wheel(output_dir: Path, *build_args: str, pattern: str) -> Path:
  """Build one workspace wheel and require exactly one matching artifact."""
  output_dir.mkdir(parents=True, exist_ok=True)
  result = subprocess.run(  # noqa: S603 -- the executable is discovered locally for tests.
    [uv_executable(), "build", *build_args, "--out-dir", str(output_dir)],
    cwd=ROOT,
    capture_output=True,
    text=True,
  )
  assert result.returncode == 0, f"uv build failed:\n{result.stdout}\n{result.stderr}"
  matches = list(output_dir.glob(pattern))
  assert len(matches) == 1, f"expected one {pattern} wheel, found {matches}"
  return matches[0]


def wheel_metadata(wheel: Path) -> tuple[list[str], object]:
  """Return archive members and parsed metadata for a wheel."""
  with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
    metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_name))
  return names, metadata


def venv_python(venv_dir: Path) -> Path:
  """Return the platform-specific virtual environment interpreter path."""
  bin_dir = "Scripts" if os.name == "nt" else "bin"
  executable = "python.exe" if os.name == "nt" else "python"
  return venv_dir / bin_dir / executable


def install_wheels_in_venv(venv_dir: Path, wheels: list[Path]) -> Path:
  """Install local wheels into a fresh environment and return its interpreter."""
  run_uv("venv", str(venv_dir))
  python = venv_python(venv_dir)
  run_uv("pip", "install", "--python", str(python), *(str(wheel) for wheel in wheels))
  return python


def install_wheel_in_venv(venv_dir: Path, wheel: Path) -> Path:
  """Install one wheel into a fresh environment."""
  return install_wheels_in_venv(venv_dir, [wheel])


def sanitized_environment() -> dict[str, str]:
  """Keep OS variables needed by Python while dropping project Python settings."""
  needed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
  return {name: os.environ[name] for name in needed if name in os.environ}


def run_isolated_python(
  python: Path, working_directory: Path, script: str
) -> subprocess.CompletedProcess[str]:
  """Run a script in isolated mode from a directory outside the checkout."""
  result = subprocess.run(  # noqa: S603 -- the interpreter is created by the test.
    [str(python), "-I", "-c", script],
    cwd=working_directory,
    env=sanitized_environment(),
    capture_output=True,
    text=True,
  )
  assert result.returncode == 0, f"isolated Python probe failed:\n{result.stdout}\n{result.stderr}"
  return result


def lockfile() -> dict[str, object]:
  """Return the parsed committed uv.lock."""
  return load_pyproject(ROOT / "uv.lock")


def locked_packages(name: str) -> list[dict[str, object]]:
  """Return every uv.lock package table for one distribution name."""
  normalized = normalize_name(name)
  return [
    package for package in lockfile()["package"] if normalize_name(package["name"]) == normalized
  ]


def locked_package(name: str) -> dict[str, object]:
  """Return the single uv.lock package table for a distribution, failing on ambiguity."""
  packages = locked_packages(name)
  assert len(packages) == 1, f"expected one locked {name} package, found {len(packages)}"
  return packages[0]


def locked_package_versions(name: str) -> list[str]:
  """Return every locked version of one distribution (empty when it is not locked)."""
  return [str(package["version"]) for package in locked_packages(name)]


def release_tuple(version: str) -> tuple[int, ...]:
  """Return the leading numeric release components of a version string."""
  release = re.match(r"^\d+(?:\.\d+)*", version)
  assert release is not None, f"unparsable version: {version!r}"
  return tuple(int(part) for part in release.group(0).split("."))


def exported_requirements(*extras: str) -> dict[str, str]:
  """Export the locked non-dev runtime selection and return its pinned versions by name."""
  extra_args = [argument for extra in extras for argument in ("--extra", extra)]
  result = run_uv(
    "export",
    "--locked",
    "--no-dev",
    "--no-emit-local",
    "--no-hashes",
    "--no-header",
    "--no-annotate",
    *extra_args,
  )
  pins: dict[str, str] = {}
  for line in result.stdout.splitlines():
    requirement = line.split(";", maxsplit=1)[0].strip()
    if not requirement or requirement.startswith(("#", "-")):
      continue
    name, separator, version = requirement.partition("==")
    assert separator, f"unexpected export line: {line!r}"
    pins[dependency_name(name)] = version.strip()
  return pins


def locked_versions() -> dict[str, str]:
  """Return workspace, PTB, SQLAlchemy, and Tornado versions from uv.lock."""
  locked = {package["name"]: package["version"] for package in lockfile()["package"]}
  names = (
    "stickfix-bot",
    "stickfix-domain",
    "stickfix-application",
    "python-telegram-bot",
    "sqlalchemy",
    "tornado",
  )
  return {name: locked[name] for name in names}


def build_isolated_application_interpreter(tmp_path: Path) -> Path:
  """Build and install the domain and application wheels together."""
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


def run_application_import_probe(
  python: Path, working_directory: Path
) -> subprocess.CompletedProcess[str]:
  """Probe the application wheel for forbidden runtime imports."""
  script = (
    "import sys\n"
    "import stickfix_application\n"
    "import stickfix_application.errors\n"
    "import stickfix_application.requests\n"
    "import stickfix_application.results\n"
    "import stickfix_application.ports\n"
    "import stickfix_application.use_cases\n"
    "assert stickfix_application.use_cases.AddSticker is not None\n"
    "forbidden = ('telegram', 'sqlalchemy', 'psycopg', 'bot')\n"
    "loaded = sorted(name for name in forbidden if name in sys.modules)\n"
    "print(','.join(loaded))\n"
  )
  return subprocess.run(  # noqa: S603 -- the interpreter is created by the test.
    [str(python), "-c", script],
    cwd=working_directory,
    capture_output=True,
    text=True,
  )
