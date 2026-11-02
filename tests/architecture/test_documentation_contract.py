"""Documentation regressions for commands and verification workflows (Phase D.3).

Each check targets a stale command that actually shipped, or a fact maintainers need to reproduce
the verified workspace, packaging, and container workflows. The checks match substrings: they do
not parse Markdown or impose one template, so rewording is free as long as the facts remain.
Per-distribution build commands come from ``dependency_policy.build_order()``, so a new
workspace member is expected in CONTRIBUTING.md as soon as it joins ``WORKSPACE_GRAPH``.

Source license notices are checked here too: ``LICENSE`` is BSD-2-Clause, and any per-file notice
must be the ``SPDX-License-Identifier: BSD-2-Clause`` line rather than a different license.

When a workflow changes on purpose (for example the Milestone 4.6 entrypoint), update the
documents and the matching expectations here in the same change.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dependency_policy import build_order
from package_contract_support import ROOT, UV_VERSION

DOCUMENTS = ("README.md", "CONTRIBUTING.md", "AGENTS.md")
STALE_COMMANDS = ("python -m bot.stickfix", "uv python use", "pytest -- -k")
LOCKED_CHECKS = (
  "uv lock --check",
  "uv sync --all-packages --locked",
  "uv run --locked ruff check .",
  "uv run --locked ruff format --check .",
  "uv run --locked pytest",
)


def document(name: str) -> str:
  """Return a repository document's text."""
  return (ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", DOCUMENTS)
def test_documents_do_not_reference_stale_commands(name: str) -> None:
  """Given the documented commands, none refers to an unsupported entrypoint or uv syntax."""
  text = document(name)

  assert [command for command in STALE_COMMANDS if command in text] == []


def test_readme_documents_the_supported_local_commands() -> None:
  """The README quick commands use the real entrypoint and supported uv syntax."""
  text = document("README.md")

  assert "uv run --locked python -m bot\n" in text
  assert "uv python pin 3.14" in text
  assert "pytest -k <pattern>" in text
  assert "CONTRIBUTING.md" in text


@pytest.mark.parametrize(
  "fact",
  [
    *LOCKED_CHECKS,
    *(f"uv build --package {name}" for name in build_order()),
    ".github/workflows/ci.yml",
    "`quality`",
    "`postgres-contract`",
    "`container`",
    "tests/architecture/container_smoke.py",
    "test_root_distribution.py",
    "UV_NO_SYNC=1",
    f"uv {UV_VERSION}",
    "--no-dev",
    "#dependency-policy",
    "Milestone 4",
    "byte-for-byte",
  ],
)
def test_contributing_documents_the_verification_workflow(fact: str) -> None:
  """CONTRIBUTING.md explains the locked, packaging, container, and CI verification workflow."""
  assert fact in document("CONTRIBUTING.md")


@pytest.mark.parametrize("command", LOCKED_CHECKS)
def test_agents_lists_the_locked_verification_commands(command: str) -> None:
  """AGENTS.md lists the same locked verification commands as CI."""
  assert command in document("AGENTS.md")


def test_agents_requires_container_and_wheel_assurance_for_package_changes() -> None:
  """AGENTS.md tells agents to keep the image build inputs and artifact tests current."""
  text = document("AGENTS.md")

  assert "Dockerfile" in text
  assert "test_container_contract.py" in text
  assert "test_root_distribution.py" in text


def python_sources() -> list[Path]:
  """Return the repository's own Python sources, excluding this module's search literals."""
  roots = [ROOT / "bot", ROOT / "alembic", ROOT / "tests", *ROOT.glob("packages/*/src")]
  roots += ROOT.glob("packages/*/tests")
  modules = [ROOT / "imghdr.py", *(path for root in roots for path in root.rglob("*.py"))]
  return [path for path in modules if path.resolve() != Path(__file__).resolve()]


def test_source_license_notices_agree_with_the_bsd_2_clause_license() -> None:
  """Source files carry no conflicting license notice; any SPDX tag names BSD-2-Clause."""
  assert document("LICENSE").startswith('BSD 2-Clause "Simplified" License')
  nonconformances = [
    f"{path.relative_to(ROOT).as_posix()}:{number}: {line.strip()}"
    for path in python_sources()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
    if "Creative Commons" in line
    or ("SPDX-License-Identifier:" in line and not line.rstrip().endswith(": BSD-2-Clause"))
  ]

  assert nonconformances == []


def test_pyproject_compatibility_comments_stay_on_the_ptb_constraints() -> None:
  """PTB pins carry their own trailing comments; nothing is attached to the PyYAML requirement.

  TOML formatters attach a standalone comment inside an array to the previous element, so each
  compatibility pin explains itself on its own line instead of under a shared heading comment.
  """
  lines = [line.strip() for line in document("pyproject.toml").splitlines()]
  comments = {line.split('"')[1].split(">")[0]: line for line in lines if line.startswith('"')}

  assert "#" not in comments["PyYAML"]
  for pin in ("urllib3", "six"):
    assert "PTB 13 compat" in comments[pin] and "dependency_policy.py" in comments[pin]
