"""Executable dependency rules for Stickfix's layered architecture."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]

FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
    "bot.domain": (
        "telegram",
        "bot.application",
        "bot.handlers",
        "bot.infrastructure",
        "bot.utils",
        "bot.database",
        "logging",
    ),
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


def python_modules(package: str) -> list[Path]:
    return list((ROOT / Path(package.replace(".", "/"))).rglob("*.py"))


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return modules


def violates(module: str, forbidden: str) -> bool:
    return module == forbidden or module.startswith(f"{forbidden}.")


@pytest.mark.parametrize("package", FORBIDDEN_IMPORTS)
def test_layer_dependency_rules(package: str) -> None:
    violations: list[str] = []
    forbidden = FORBIDDEN_IMPORTS[package]

    for path in python_modules(package):
        relative = path.relative_to(ROOT).with_suffix("")
        importing = ".".join(relative.parts)
        for imported in imported_modules(path):
            if any(violates(imported, rule) for rule in forbidden):
                violations.append(
                    f"{importing} imports {imported}; forbidden by {package} dependency rule"
                )

    assert not violations, "\n".join(violations)


def test_runtime_composition_does_not_import_migration_infrastructure() -> None:
    """The normal runtime graph must not load the one-shot migration path."""
    runtime_imports = imported_modules(ROOT / "bot" / "stickfix.py")

    violations = [
        imported
        for imported in runtime_imports
        if violates(imported, "bot.infrastructure.migration")
    ]

    assert not violations, "runtime composition imports migration infrastructure: " + ", ".join(
        violations
    )
