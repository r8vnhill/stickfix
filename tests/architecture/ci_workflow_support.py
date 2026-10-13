"""Read-only helpers for inspecting ``.github/workflows/ci.yml`` in contract tests.

Workflow contracts (``test_workspace_contract.py``, ``test_container_contract.py``) assert on step
commands and effective environments. These helpers expose exactly that: they are not a GitHub
Actions interpreter, and only resolve the ``${{ env.NAME }}`` references the workflow uses.
"""

from __future__ import annotations

import re

import yaml
from conftest import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
ENV_REFERENCE = re.compile(r"\$\{\{\s*env\.(?P<name>\w+)\s*\}\}")

Job = dict[str, object]
Step = dict[str, object]


def workflow_jobs() -> dict[str, Job]:
  """Return the ``jobs`` mapping, avoiding PyYAML's boolean reading of the top-level ``on`` key."""
  return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def run_commands(job: Job) -> list[str]:
  """Return each step's ``run`` command with whitespace collapsed, in step order."""
  return [" ".join(step["run"].split()) for step in job["steps"] if "run" in step]


def effective_env(job: Job, step: Step) -> dict[str, str]:
  """Merge job and step environments as Actions does, resolving ``${{ env.NAME }}`` references."""
  job_env = {name: str(value) for name, value in job.get("env", {}).items()}
  step_env = {
    name: ENV_REFERENCE.sub(lambda match: job_env.get(match["name"], ""), str(value))
    for name, value in step.get("env", {}).items()
  }
  return {**job_env, **step_env}
