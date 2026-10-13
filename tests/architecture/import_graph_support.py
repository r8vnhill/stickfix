"""Reusable AST import scanner for architecture and dependency-ownership tests.

The scanner accepts both the legacy flat ``bot`` layout and workspace members
using ``src`` roots. It only extracts normalized import edges; each test module
decides which edges conform to its own rules.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


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
