"""Guard the Python baseline and indentation contract for maintainer tooling."""

from __future__ import annotations

import tomllib

from package_contract_support import ROOT


def test_python_tooling_matches_project_baseline() -> None:
  """The project, Ruff, and EditorConfig agree on Python 3.14 and two-space indentation."""
  project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
  ruff = tomllib.loads((ROOT / "ruff.toml").read_text(encoding="utf-8"))
  editorconfig = (ROOT / ".editorconfig").read_text(encoding="utf-8")
  python_section = editorconfig.split("[*.{py,pyi}]", 1)[1].split("\n[", 1)[0]
  editor_values = {}
  for line in python_section.splitlines():
    if "=" in line:
      key, value = line.split("=", 1)
      editor_values[key.strip()] = value.strip()

  assert project["project"]["requires-python"] == ">=3.14,<4"
  assert ruff["target-version"] == "py314"
  assert ruff["indent-width"] == 2
  assert editor_values["indent_size"] == "2"
