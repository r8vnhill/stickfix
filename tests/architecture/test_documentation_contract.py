"""Documentation regressions for commands and verification workflows (Phase D.3).

Each check targets a stale command that actually shipped, or a fact maintainers need to reproduce
the verified workspace, packaging, and container workflows. The checks match substrings: they do
not parse Markdown or impose one template, so rewording is free as long as the facts remain.

When a workflow changes on purpose (for example the Milestone 4.6 entrypoint), update the
documents and the matching expectations here in the same change.
"""

from __future__ import annotations

import pytest
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
    "uv build --package stickfix-domain",
    "uv build --package stickfix-application",
    "uv build --package stickfix-bot",
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


def test_pyproject_compatibility_comment_introduces_the_ptb_constraints() -> None:
  """The PTB compatibility comment is not attached to the unrelated PyYAML requirement."""
  lines = document("pyproject.toml").splitlines()
  pyyaml = next(line for line in lines if line.strip().startswith('"PyYAML'))
  urllib3 = next(index for index, line in enumerate(lines) if line.strip().startswith('"urllib3'))

  assert "#" not in pyyaml
  assert "PTB 13 compatibility constraints" in lines[urllib3 - 1]
