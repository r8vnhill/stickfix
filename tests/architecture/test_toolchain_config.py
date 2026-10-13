"""Guard the Python baseline and formatting contract shared by maintainer tooling.

``pyproject.toml``, ``ruff.toml``, and ``.editorconfig`` must agree on Python 3.14 and two-space
indentation (Phase C). Ruff 0.17 also formats Python code blocks inside Markdown; historical
traceability records are excluded so closed records keep the snippets they were written with.
"""

from __future__ import annotations

from package_contract_support import ROOT, load_pyproject, project_metadata


def ruff_config() -> dict[str, object]:
  """Return the parsed repository ``ruff.toml``."""
  return load_pyproject(ROOT / "ruff.toml")


def editorconfig_section(pattern: str) -> dict[str, str]:
  """Return the ``key = value`` settings of one ``.editorconfig`` section."""
  text = (ROOT / ".editorconfig").read_text(encoding="utf-8")
  section = text.split(f"[{pattern}]", 1)[1].split("\n[", 1)[0]
  pairs = (line.split("=", 1) for line in section.splitlines() if "=" in line)
  return {key.strip(): value.strip() for key, value in pairs}


def test_python_tooling_matches_project_baseline() -> None:
  """The project, Ruff, and EditorConfig agree on Python 3.14 and two-space indentation."""
  ruff = ruff_config()

  assert project_metadata()["project"]["requires-python"] == ">=3.14,<4"
  assert ruff["target-version"] == "py314"
  assert ruff["indent-width"] == 2
  assert editorconfig_section("*.{py,pyi}")["indent_size"] == "2"


def test_ruff_leaves_historical_traceability_records_unformatted() -> None:
  """Ruff formats Markdown code blocks, but traceability records keep their original snippets."""
  assert "traceability-log" in ruff_config().get("extend-exclude", [])
