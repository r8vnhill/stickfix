"""AST checks for package boundaries and forbidden import directions.

The shared scanner in ``import_graph_support`` accepts both the legacy flat ``bot`` layout and
workspace members using ``src`` roots. Rules here are intentionally stricter than importability:
they describe which layers a package is allowed to know about, so a passing editable install is
never taken as evidence that a boundary holds.

Maintainers change the rules through the tables below, not inside individual tests:

- ``MEMBER_ALLOWED_IMPORTS``: the non-stdlib import roots each workspace member may reach;
- ``FORBIDDEN_IMPORTS``: module prefixes that a ``bot.*`` package must never import;
- ``REMOVED_BOT_NAMESPACES``: legacy namespaces deleted by a cutover, which keeps no shims;
- ``IDENTITY_MODULE`` and ``TELEGRAM_ADAPTER_NAMESPACES``: who may convert Telegram callers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conftest import ROOT
from dependency_policy import WORKSPACE_MEMBERS
from import_graph_support import (
  ImportEdge,
  PackageBoundary,
  boundary_edges,
  describe_edge,
  import_edges,
  matches_any_prefix,
  matches_forbidden_prefix,
  module_name,
)
from package_contract_support import member_boundary

BOT = PackageBoundary(namespace="bot", source_root=ROOT)
PRODUCTION_BOUNDARIES = (BOT, *map(member_boundary, WORKSPACE_MEMBERS))
# Besides the standard library, each member may import exactly these roots (itself included).
MEMBER_ALLOWED_IMPORTS: dict[str, tuple[str, ...]] = {
  "stickfix-domain": ("stickfix_domain",),
  "stickfix-application": ("stickfix_application", "stickfix_domain", "expression"),
  # Milestone 4.5 target edges: runtime composition and infrastructure stay out of the adapters.
  "stickfix-telegram": (
    "stickfix_telegram",
    "stickfix_application",
    "stickfix_domain",
    "telegram",
  ),
}
# Telegram-to-domain caller identity conversion and the adapters allowed to consume it.
# ``bot.handlers`` leaves this tuple once the handlers move into ``stickfix_telegram``.
IDENTITY_MODULE = "stickfix_telegram.identity"
TELEGRAM_ADAPTER_NAMESPACES = ("bot.handlers", "stickfix_telegram")
REMOVED_BOT_NAMESPACES = ("bot.domain", "bot.application", "bot.handlers.common")

FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
  # Telegram adapters receive collaborators from runtime composition; they never reach back
  # into runtime configuration, composition, or any infrastructure adapter.
  "bot.handlers": (
    "bot.stickfix",
    "bot.config",
    "bot.infrastructure",
    "bot.database",
    "sqlalchemy",
    "psycopg",
  ),
}


def describe(edges: list[ImportEdge]) -> str:
  """Join nonconforming edges into one assertion message, one edge per line."""
  return "\n".join(map(describe_edge, edges))


@pytest.mark.parametrize("package", FORBIDDEN_IMPORTS)
def test_layer_dependency_rules(package: str) -> None:
  """Each ``bot.*`` package rule rejects imports of its forbidden module prefixes."""
  boundary = PackageBoundary(namespace=package, source_root=ROOT)
  nonconformances = [
    edge
    for edge in boundary_edges(boundary)
    if matches_any_prefix(edge.imported, FORBIDDEN_IMPORTS[package])
  ]

  assert not nonconformances, f"forbidden by the {package} rule:\n{describe(nonconformances)}"


def test_every_workspace_member_has_an_import_allowlist() -> None:
  """A new member cannot join the workspace without declaring the imports it may make."""
  assert set(MEMBER_ALLOWED_IMPORTS) == set(WORKSPACE_MEMBERS)


@pytest.mark.parametrize("member", MEMBER_ALLOWED_IMPORTS)
def test_member_absolute_imports_are_limited_to_an_explicit_allowlist(member: str) -> None:
  """A workspace member reaches only the standard library and its allowlisted import roots."""
  edges = boundary_edges(member_boundary(member))
  nonconformances = [
    edge
    for edge in edges
    if edge.imported.partition(".")[0] not in sys.stdlib_module_names
    and not matches_any_prefix(edge.imported, MEMBER_ALLOWED_IMPORTS[member])
  ]

  assert edges, f"{member} has no import edges to check"
  assert not nonconformances, describe(nonconformances)


def test_domain_excludes_logging_despite_being_stdlib() -> None:
  """The domain contract deliberately excludes logging as an effect."""
  nonconformances = [
    edge
    for edge in boundary_edges(member_boundary("stickfix-domain"))
    if matches_forbidden_prefix(edge.imported, "logging")
  ]

  assert not nonconformances, describe(nonconformances)


def test_identity_conversion_is_consumed_only_by_telegram_adapters() -> None:
  """Caller identity is a Telegram boundary concern; no other layer converts updates."""
  consumers = [
    edge
    for edge in boundary_edges(*PRODUCTION_BOUNDARIES)
    if matches_forbidden_prefix(edge.imported, IDENTITY_MODULE)
  ]
  nonconformances = [
    edge for edge in consumers if not matches_any_prefix(edge.importer, TELEGRAM_ADAPTER_NAMESPACES)
  ]

  assert consumers, f"no production module imports {IDENTITY_MODULE}"
  assert not nonconformances, describe(nonconformances)


@pytest.mark.parametrize("removed_namespace", REMOVED_BOT_NAMESPACES)
def test_no_production_module_imports_a_removed_bot_namespace(removed_namespace: str) -> None:
  """The namespace cutovers left no production import edge into removed ``bot.*`` packages."""
  nonconformances = [
    edge
    for edge in boundary_edges(BOT)
    if matches_forbidden_prefix(edge.imported, removed_namespace)
  ]

  assert not nonconformances, describe(nonconformances)


def test_scanner_derives_current_flat_layout_module_names() -> None:
  """The current repository layout remains supported by explicit boundaries."""
  boundary = PackageBoundary(namespace="bot.handlers", source_root=ROOT)

  assert module_name(ROOT / "bot" / "handlers" / "stickers.py", boundary) == (
    "bot.handlers.stickers"
  )
  assert module_name(ROOT / "bot" / "handlers" / "inline.py", boundary) == "bot.handlers.inline"


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
  nonconformances = [
    edge
    for edge in import_edges(ROOT / "bot" / "stickfix.py", BOT)
    if matches_forbidden_prefix(edge.imported, "bot.infrastructure.migration")
  ]

  assert not nonconformances, describe(nonconformances)
