"""Root wheel coverage and non-editable runtime installation contracts.

These tests protect the complete current ``bot`` package tree and prove that
the three workspace wheels work outside the source checkout with locked runtime
dependencies.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from package_contract_support import (
  DEV_DEPENDENCIES,
  OPTIONAL_DEPENDENCIES,
  ROOT,
  build_wheel,
  dependency_name,
  locked_versions,
  named_dependencies,
  project_metadata,
  run_isolated_python,
  run_uv,
  wheel_metadata,
)

REPRESENTATIVE_MODULES = {
  "bot/__init__.py",
  "bot/__main__.py",
  "bot/config.py",
  "bot/stickfix.py",
  "bot/handlers/common.py",
  "bot/handlers/inline.py",
  "bot/handlers/stickers.py",
  "bot/handlers/utility.py",
  "bot/infrastructure/help/file_help_content_provider.py",
  "bot/infrastructure/logging/configuration.py",
  "bot/infrastructure/migration/yaml_to_postgres.py",
  "bot/infrastructure/persistence/postgres/repositories.py",
  "bot/utils/messages.py",
  "imghdr.py",
}
EXCLUDED_PREFIXES = (
  "tests/",
  "data/",
  "logs/",
  "packages/",
  "stickfix_domain/",
  "stickfix_application/",
)
RUNTIME_MODULES = (
  "bot.stickfix",
  "bot.__main__",
  "bot.config",
  "bot.handlers.inline",
  "bot.handlers.stickers",
  "bot.handlers.utility",
  "bot.infrastructure.help",
  "bot.infrastructure.logging",
  "bot.infrastructure.persistence.postgres",
  "bot.infrastructure.migration.yaml_to_postgres",
  "stickfix_domain",
  "stickfix_application",
  "imghdr",
)
ORIGIN_PROBE = """
import importlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

module_names = json.loads(@MODULES@)
repository = Path(@REPOSITORY@).resolve()
environment = Path(sys.prefix).resolve()
origins = {}
for name in module_names:
    module = importlib.import_module(name)
    origin = getattr(module, '__file__', None) or module.__spec__.origin
    assert origin and origin != 'namespace', (name, origin)
    path = Path(origin).resolve()
    assert path.is_relative_to(environment), (name, path, environment)
    assert not path.is_relative_to(repository), (name, path, repository)
    origins[name] = str(path)

compatibility = importlib.import_module('imghdr')
origin = Path(compatibility.__file__).resolve()
assert origin == Path(metadata.distribution('stickfix-bot').locate_file('imghdr.py')).resolve()
assert compatibility.what() is None
assert compatibility.what(b'GIF89a') is None
assert compatibility.what(h=b'GIF89a') is None
print(json.dumps(origins, sort_keys=True))
"""
VERSION_PROBE = """
import importlib.metadata as metadata
import json

expected = json.loads(@EXPECTED@)
versions = {name: metadata.version(name) for name in expected}
installed = {item.metadata['Name'].lower().replace('_', '-') for item in metadata.distributions()}
forbidden = json.loads(@FORBIDDEN@)
assert not installed.intersection(forbidden)
assert versions == expected, (versions, expected)
print(json.dumps(versions, sort_keys=True))
"""


def _expected_bot_modules() -> set[str]:
  """Derive expected wheel members from every current bot Python source file."""
  return {path.relative_to(ROOT).as_posix() for path in (ROOT / "bot").rglob("*.py")}


def _assert_runtime_tree(names: list[str]) -> None:
  """Require every production module and reject known repository-only paths."""
  archive_names = set(names)
  assert _expected_bot_modules() | REPRESENTATIVE_MODULES <= archive_names
  assert not any(name.startswith(EXCLUDED_PREFIXES) for name in names)


def _assert_published_metadata(metadata: object) -> None:
  """Keep root runtime requirements and optional-extra names equal to project metadata."""
  project = project_metadata()["project"]
  requirements = metadata.get_all("Requires-Dist", [])
  runtime_names = named_dependencies(project["dependencies"])
  published_runtime = {
    dependency_name(req) for req in requirements if not re.search(r";\s*extra\s*==", req)
  }
  assert published_runtime == runtime_names
  extras = project["optional-dependencies"]
  assert set(metadata.get_all("Provides-Extra", [])) == set(extras)
  _assert_published_extras(requirements, extras)


def _assert_published_extras(requirements: list[str], extras: dict[str, list[str]]) -> None:
  """Check each wheel extra publishes the configured dependency names."""
  for extra, dependencies in extras.items():
    published = {
      dependency_name(req)
      for req in requirements
      if re.search(rf";\s*extra\s*==\s*['\"]{re.escape(extra)}['\"]", req)
    }
    assert published == named_dependencies(dependencies)


def test_root_wheel_contains_complete_runtime_tree(tmp_path: Path) -> None:
  """The root wheel contains all bot modules and retains its published metadata."""
  wheel = build_wheel(
    tmp_path,
    "--wheel",
    "--package",
    "stickfix-bot",
    pattern="stickfix_bot-*.whl",
  )
  names, metadata = wheel_metadata(wheel)

  _assert_runtime_tree(names)
  _assert_published_metadata(metadata)


def _build_workspace_wheels(temporary_root: Path) -> list[Path]:
  """Build one local wheel for each current workspace distribution."""
  specifications = (
    ("stickfix-domain", "stickfix_domain-*.whl"),
    ("stickfix-application", "stickfix_application-*.whl"),
    ("stickfix-bot", "stickfix_bot-*.whl"),
  )
  return [
    build_wheel(
      temporary_root / "dist",
      "--wheel",
      "--package",
      package,
      pattern=pattern,
    )
    for package, pattern in specifications
  ]


def _assert_locked_requirements(requirements: Path) -> None:
  """Require exported third-party runtime pins without workspace, dev, or extra packages."""
  text = requirements.read_text(encoding="utf-8")
  names = {
    dependency_name(line.split(";", maxsplit=1)[0].split("\\", maxsplit=1)[0])
    for line in text.splitlines()
    if line.strip() and not line.lstrip().startswith(("#", "--"))
  }
  internal = {"stickfix-bot", "stickfix-domain", "stickfix-application"}
  runtime = named_dependencies(project_metadata()["project"]["dependencies"])
  assert runtime - internal <= names
  assert not DEV_DEPENDENCIES & names
  assert not OPTIONAL_DEPENDENCIES & names
  assert not internal & names
  assert str(ROOT.resolve()) not in text and "file://" not in text
  assert "--hash=sha256:" in text


def _export_locked_requirements(temporary_root: Path) -> Path:
  """Export hashed, normal runtime requirements from the committed lockfile."""
  requirements = temporary_root / "runtime-requirements.txt"
  run_uv(
    "export",
    "--locked",
    "--no-dev",
    "--no-emit-local",
    "--output-file",
    str(requirements),
  )
  _assert_locked_requirements(requirements)
  return requirements


def _install_locked_runtime(temporary_root: Path, requirements: Path, wheels: list[Path]) -> Path:
  """Install pinned third-party requirements and then the local wheels without resolution."""
  venv = temporary_root / "venv"
  run_uv("venv", "--python", "3.14", str(venv))
  python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  run_uv("pip", "sync", "--python", str(python), str(requirements))
  run_uv("pip", "install", "--python", str(python), "--no-deps", *(str(w) for w in wheels))
  return python


@pytest.fixture(scope="module")
def installed_runtime(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
  """Build and install all workspace wheels outside the checkout with locked dependencies."""
  temporary_root = tmp_path_factory.mktemp("installed-runtime")
  assert not temporary_root.resolve().is_relative_to(ROOT.resolve())
  wheels = _build_workspace_wheels(temporary_root)
  requirements = _export_locked_requirements(temporary_root)
  python = _install_locked_runtime(temporary_root, requirements, wheels)
  return python, temporary_root


def _version_probe(expected: dict[str, str]) -> str:
  """Create a probe for distribution versions and forbidden dev or optional packages."""
  forbidden = sorted(DEV_DEPENDENCIES | OPTIONAL_DEPENDENCIES)
  return VERSION_PROBE.replace("@EXPECTED@", repr(json.dumps(expected))).replace(
    "@FORBIDDEN@", repr(json.dumps(forbidden))
  )


def test_locked_install_uses_workspace_and_runtime_versions(
  installed_runtime: tuple[Path, Path],
) -> None:
  """Installed package identities and selected dependency versions match uv.lock."""
  python, working_directory = installed_runtime
  expected = locked_versions()
  result = run_isolated_python(python, working_directory, _version_probe(expected))

  assert json.loads(result.stdout) == expected


def _origin_probe() -> str:
  """Bind the module origin probe to this checkout and its explicit import targets."""
  return ORIGIN_PROBE.replace("@MODULES@", repr(json.dumps(RUNTIME_MODULES))).replace(
    "@REPOSITORY@", repr(str(ROOT.resolve()))
  )


def test_runtime_imports_resolve_from_the_isolated_wheels(
  installed_runtime: tuple[Path, Path],
) -> None:
  """Runtime, handler, infrastructure, domain, and app imports resolve inside the venv."""
  python, working_directory = installed_runtime
  result = run_isolated_python(python, working_directory, _origin_probe())

  assert set(json.loads(result.stdout)) == set(RUNTIME_MODULES)
