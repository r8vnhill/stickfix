"""AST checks for package boundaries and forbidden import directions.

The scanner accepts both the legacy flat ``bot`` layout and workspace members
using ``src`` roots. Rules here are intentionally stricter than importability:
they describe which layers a package is allowed to know about.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import ROOT

DOMAIN_SOURCE_ROOT = ROOT / "packages" / "stickfix-domain" / "src"

FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
  "bot.application": (
    "telegram",
    "bot.handlers",
    "bot.infrastructure",
    "bot.database",
    "sqlalchemy",
    "psycopg",
  ),
  "bot.handlers": (
    "bot.infrastructure.persistence",
    "bot.infrastructure.migration",
    "bot.database",
    "sqlalchemy",
    "psycopg",
  ),
}


@dataclass(frozen=True)
class PackageBoundary:
  """An import namespace and the source root that supplies it."""

  namespace: str
  source_root: Path

  @property
  def package_root(self) -> Path:
    """Return the filesystem root of the bounded Python package."""
    return self.source_root.joinpath(*self.namespace.split("."))


@dataclass(frozen=True)
class ImportEdge:
  """A normalized import emitted by one Python source module."""

  importer: str
  imported: str
  path: Path
  line: int


def python_modules(boundary: PackageBoundary) -> list[Path]:
  """Discover Python modules below an explicit package boundary."""
  return sorted(boundary.package_root.rglob("*.py"))


def module_name(path: Path, boundary: PackageBoundary) -> str:
  """Derive an importable module name from a path within a boundary."""
  relative = path.relative_to(boundary.package_root).with_suffix("")
  parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
  return ".".join((boundary.namespace, *parts))


def importing_package(path: Path, boundary: PackageBoundary) -> str:
  """Return the package against which relative imports in a module resolve."""
  name = module_name(path, boundary)
  return name if path.stem == "__init__" else name.rpartition(".")[0]


def resolve_from_import(node: ast.ImportFrom, package: str) -> str | None:
  """Resolve an ``ImportFrom`` node to its absolute imported module name."""
  if node.level == 0:
    return node.module

  package_parts = package.split(".")
  parent_parts = package_parts[: len(package_parts) - node.level + 1]
  if not parent_parts:
    return None
  module_parts = () if node.module is None else tuple(node.module.split("."))
  return ".".join((*parent_parts, *module_parts))


def import_edges(path: Path, boundary: PackageBoundary) -> list[ImportEdge]:
  """Extract normalized absolute import edges from one Python module."""
  tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  importer = module_name(path, boundary)
  package = importing_package(path, boundary)
  edges: list[ImportEdge] = []
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      edges.extend(ImportEdge(importer, alias.name, path, node.lineno) for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
      imported = resolve_from_import(node, package)
      if imported is not None:
        edges.append(ImportEdge(importer, imported, path, node.lineno))
  return edges


def matches_forbidden_prefix(module: str, forbidden: str) -> bool:
  """Return whether an imported module is the forbidden module or a descendant."""
  return module == forbidden or module.startswith(f"{forbidden}.")


@pytest.mark.parametrize("package", FORBIDDEN_IMPORTS)
def test_layer_dependency_rules(package: str) -> None:
  """Current package rules remain effective through the reusable scanner."""
  boundary = PackageBoundary(namespace=package, source_root=ROOT)
  forbidden = FORBIDDEN_IMPORTS[package]
  nonconformances = [
    (
      f"{edge.path}:{edge.line}: {edge.importer} imports {edge.imported}; "
      f"forbidden by {package} dependency rule"
    )
    for path in python_modules(boundary)
    for edge in import_edges(path, boundary)
    if any(matches_forbidden_prefix(edge.imported, rule) for rule in forbidden)
  ]

  assert not nonconformances, "\n".join(nonconformances)


def test_domain_absolute_imports_are_limited_to_the_standard_library() -> None:
  """stickfix-domain stays infrastructure-free: every external import is stdlib."""
  boundary = PackageBoundary(namespace="stickfix_domain", source_root=DOMAIN_SOURCE_ROOT)
  nonconformances = [
    f"{edge.path}:{edge.line}: {edge.importer} imports {edge.imported}"
    for path in python_modules(boundary)
    for edge in import_edges(path, boundary)
    if edge.imported.partition(".")[0] not in sys.stdlib_module_names
    and not matches_forbidden_prefix(edge.imported, "stickfix_domain")
  ]

  assert not nonconformances, "\n".join(nonconformances)


def test_domain_excludes_logging_despite_being_stdlib() -> None:
  """The domain contract deliberately excludes logging as an effect."""
  boundary = PackageBoundary(namespace="stickfix_domain", source_root=DOMAIN_SOURCE_ROOT)
  nonconformances = [
    f"{edge.path}:{edge.line}: {edge.importer} imports {edge.imported}"
    for path in python_modules(boundary)
    for edge in import_edges(path, boundary)
    if matches_forbidden_prefix(edge.imported, "logging")
  ]

  assert not nonconformances, "\n".join(nonconformances)


def test_no_production_module_imports_the_removed_bot_domain_namespace() -> None:
  """The namespace cutover left no production import edge into ``bot.domain``."""
  boundary = PackageBoundary(namespace="bot", source_root=ROOT)
  nonconformances = [
    f"{edge.path}:{edge.line}: {edge.importer} imports {edge.imported}"
    for path in python_modules(boundary)
    for edge in import_edges(path, boundary)
    if matches_forbidden_prefix(edge.imported, "bot.domain")
  ]

  assert not nonconformances, "\n".join(nonconformances)


def test_scanner_derives_current_flat_layout_module_names() -> None:
  """The current repository layout remains supported by explicit boundaries."""
  boundary = PackageBoundary(namespace="bot.application", source_root=ROOT)

  assert module_name(ROOT / "bot" / "application" / "requests.py", boundary) == (
    "bot.application.requests"
  )
  assert module_name(ROOT / "bot" / "application" / "__init__.py", boundary) == "bot.application"


def test_scanner_derives_src_layout_module_names(tmp_path: Path) -> None:
  """The same scanner supports a future workspace package's src layout."""
  source_root = tmp_path / "packages" / "stickfix-domain" / "src"
  package_root = source_root / "stickfix_domain" / "services"
  package_root.mkdir(parents=True)
  module = package_root / "resolver.py"
  module.write_text("from . import helpers\n", encoding="utf-8")
  initializer = package_root / "__init__.py"
  initializer.write_text("", encoding="utf-8")
  boundary = PackageBoundary(namespace="stickfix_domain", source_root=source_root)

  assert module_name(module, boundary) == "stickfix_domain.services.resolver"
  assert module_name(initializer, boundary) == "stickfix_domain.services"


def test_relative_imports_are_resolved_before_dependency_evaluation(tmp_path: Path) -> None:
  """A forbidden relative import is reported as its absolute import edge."""
  source_root = tmp_path / "src"
  application = source_root / "bot" / "application"
  application.mkdir(parents=True)
  module = application / "use_case.py"
  module.write_text(
    "from ..infrastructure import persistence\nfrom . import ports\n", encoding="utf-8"
  )
  boundary = PackageBoundary(namespace="bot.application", source_root=source_root)

  edges = import_edges(module, boundary)
  imported_modules = {edge.imported for edge in edges}
  nonconformances = [
    edge for edge in edges if matches_forbidden_prefix(edge.imported, "bot.infrastructure")
  ]

  assert imported_modules == {"bot.infrastructure", "bot.application"}
  assert len(nonconformances) == 1
  assert nonconformances[0].imported == "bot.infrastructure"
  assert nonconformances[0].line == 1


def test_runtime_composition_does_not_import_migration_infrastructure() -> None:
  """The normal runtime graph must not load the one-shot migration path."""
  boundary = PackageBoundary(namespace="bot", source_root=ROOT)
  runtime_path = ROOT / "bot" / "stickfix.py"
  nonconformances = [
    edge
    for edge in import_edges(runtime_path, boundary)
    if matches_forbidden_prefix(edge.imported, "bot.infrastructure.migration")
  ]

  assert not nonconformances, "runtime composition imports migration infrastructure: " + ", ".join(
    edge.imported for edge in nonconformances
  )
