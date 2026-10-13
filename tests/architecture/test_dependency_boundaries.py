"""AST checks for package boundaries and forbidden import directions.

The shared scanner in ``import_graph_support`` accepts both the legacy flat
``bot`` layout and workspace members using ``src`` roots. Rules here are
intentionally stricter than importability: they describe which layers a
package is allowed to know about.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conftest import ROOT
from import_graph_support import (
  PackageBoundary,
  import_edges,
  matches_forbidden_prefix,
  module_name,
  python_modules,
)

DOMAIN_SOURCE_ROOT = ROOT / "packages" / "stickfix-domain" / "src"
APPLICATION_SOURCE_ROOT = ROOT / "packages" / "stickfix-application" / "src"
APPLICATION_ALLOWED_NAMESPACES = ("stickfix_application", "stickfix_domain")

FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
  "bot.handlers": (
    "bot.infrastructure.persistence",
    "bot.infrastructure.migration",
    "bot.database",
    "sqlalchemy",
    "psycopg",
  ),
}


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


def test_application_absolute_imports_are_limited_to_an_explicit_allowlist() -> None:
  """stickfix-application only ever reaches stdlib, itself, or stickfix-domain."""
  boundary = PackageBoundary(namespace="stickfix_application", source_root=APPLICATION_SOURCE_ROOT)
  nonconformances = [
    f"{edge.path}:{edge.line}: {edge.importer} imports {edge.imported}"
    for path in python_modules(boundary)
    for edge in import_edges(path, boundary)
    if edge.imported.partition(".")[0] not in sys.stdlib_module_names
    and not any(
      matches_forbidden_prefix(edge.imported, namespace)
      for namespace in APPLICATION_ALLOWED_NAMESPACES
    )
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


@pytest.mark.parametrize("removed_namespace", ["bot.domain", "bot.application"])
def test_no_production_module_imports_a_removed_bot_namespace(removed_namespace: str) -> None:
  """The namespace cutovers left no production import edge into removed ``bot.*`` packages."""
  boundary = PackageBoundary(namespace="bot", source_root=ROOT)
  nonconformances = [
    f"{edge.path}:{edge.line}: {edge.importer} imports {edge.imported}"
    for path in python_modules(boundary)
    for edge in import_edges(path, boundary)
    if matches_forbidden_prefix(edge.imported, removed_namespace)
  ]

  assert not nonconformances, "\n".join(nonconformances)


def test_scanner_derives_current_flat_layout_module_names() -> None:
  """The current repository layout remains supported by explicit boundaries."""
  boundary = PackageBoundary(namespace="bot.handlers", source_root=ROOT)

  assert module_name(ROOT / "bot" / "handlers" / "stickers.py", boundary) == (
    "bot.handlers.stickers"
  )
  assert module_name(ROOT / "bot" / "handlers" / "common.py", boundary) == "bot.handlers.common"


def test_scanner_derives_src_layout_module_names(tmp_path: Path) -> None:
  """The same scanner supports a workspace package's ``src`` layout."""
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
