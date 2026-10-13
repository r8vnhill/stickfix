"""Workspace membership, locked internal edges, and CI verification contracts (Phase D.1).

``WORKSPACE_GRAPH`` in ``dependency_policy.py`` is the recorded architecture. These tests prove
that package directories, ``[tool.uv.sources]``, and ``uv.lock`` agree with it, and that CI checks
the lock before running the locked quality and PostgreSQL steps. External dependency metadata is
covered by ``test_dependency_lock_policy.py`` and deliberately not repeated here.

When a workspace member is added or extracted (Milestone 4.5+), update ``WORKSPACE_GRAPH`` first;
these tests then point at every other place that must change.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from ci_workflow_support import effective_env, run_commands, workflow_jobs
from dependency_policy import WORKSPACE_GRAPH
from package_contract_support import (
  ROOT,
  UV_VERSION,
  load_pyproject,
  locked_package,
  lockfile,
  named_dependencies,
  project_metadata,
  workspace_member_metadata,
)

ROOT_DISTRIBUTION = "stickfix-bot"
MEMBERS = sorted(set(WORKSPACE_GRAPH) - {ROOT_DISTRIBUTION})
INTERNAL = frozenset(WORKSPACE_GRAPH)
LOCKED_JOBS = ("quality", "postgres-contract")
DATABASE_URL = "postgresql+psycopg://stickfix:stickfix-test@localhost:5432/stickfix"
StepPredicate = Callable[[str], bool]


# --- Workspace membership ---------------------------------------------------------------------


def metadata_for(distribution: str) -> dict[str, object]:
  """Return the whole parsed ``pyproject.toml`` of the root or a workspace member."""
  if distribution == ROOT_DISTRIBUTION:
    return project_metadata()
  return workspace_member_metadata(distribution)


def discovered_members() -> set[str]:
  """Return the project names of every ``packages/*`` directory that has a pyproject.toml."""
  manifests = (ROOT / "packages").glob("*/pyproject.toml")
  return {load_pyproject(path)["project"]["name"] for path in manifests}


def expected_source(distribution: str) -> dict[str, str]:
  """Return the editable workspace source uv records for a distribution."""
  path = "." if distribution == ROOT_DISTRIBUTION else f"packages/{distribution}"
  return {"editable": path}


def test_workspace_membership_matches_the_recorded_graph() -> None:
  """Given the uv workspace, members and the lock manifest identify exactly the graph."""
  metadata = project_metadata()

  assert metadata["project"]["name"] == ROOT_DISTRIBUTION
  assert metadata["tool"]["uv"]["workspace"]["members"] == ["packages/*"]
  assert discovered_members() == set(MEMBERS)
  assert set(lockfile()["manifest"]["members"]) == INTERNAL


@pytest.mark.parametrize("distribution", sorted(WORKSPACE_GRAPH))
def test_locked_workspace_identity_matches_project_metadata(distribution: str) -> None:
  """Each workspace distribution is locked at its declared version and editable source."""
  project = metadata_for(distribution)["project"]
  locked = locked_package(distribution)

  assert locked["version"] == project["version"]
  assert locked["source"] == expected_source(distribution)
  assert project["requires-python"] == project_metadata()["project"]["requires-python"]


def locked_edges(distribution: str) -> tuple[set[str], dict[str, str]]:
  """Return a distribution's locked internal edges and its editable ``requires-dist`` paths."""
  locked = locked_package(distribution)
  requires_dist = locked.get("metadata", {}).get("requires-dist", ())
  edges = {entry["name"] for entry in locked.get("dependencies", ())} & INTERNAL
  editable = {entry["name"]: entry["editable"] for entry in requires_dist if "editable" in entry}
  return edges, editable


@pytest.mark.parametrize("distribution", sorted(WORKSPACE_GRAPH))
def test_locked_internal_edges_match_the_recorded_graph(distribution: str) -> None:
  """Given a member, its declared, sourced, and locked internal edges agree with the graph."""
  metadata = metadata_for(distribution)
  expected = set(WORKSPACE_GRAPH[distribution])
  sources = metadata.get("tool", {}).get("uv", {}).get("sources", {})
  edges, editable = locked_edges(distribution)

  assert named_dependencies(metadata["project"]["dependencies"]) & INTERNAL == expected
  assert edges == expected
  assert editable == {name: f"packages/{name}" for name in expected}
  assert {name for name, source in sources.items() if source == {"workspace": True}} == expected


# --- CI workflow ------------------------------------------------------------------------------


def first_index(commands: list[str], predicate: StepPredicate, label: str) -> int:
  """Return the position of the first command matching a predicate."""
  for index, command in enumerate(commands):
    if predicate(command):
      return index
  raise AssertionError(f"CI is missing the step: {label}")


def _has(*fragments: str) -> StepPredicate:
  """Match commands containing every fragment as a whole word, in any order."""
  return lambda command: all(fragment in command.split() for fragment in fragments)


def _full_pytest(command: str) -> bool:
  """Match the unfiltered test run, not the marker-selected integration run."""
  return "pytest" in command.split() and "-m" not in command


QUALITY_SEQUENCE: tuple[tuple[str, StepPredicate], ...] = (
  ("uv lock --check", _has("uv", "lock", "--check")),
  ("uv sync --all-packages --locked", _has("uv", "sync", "--all-packages", "--locked")),
  ("ruff check", _has("ruff", "check")),
  ("ruff format --check", _has("ruff", "format", "--check")),
  ("pytest (full suite)", _full_pytest),
  ("build stickfix-domain", _has("uv", "build", "--package", "stickfix-domain")),
  ("build stickfix-application", _has("uv", "build", "--package", "stickfix-application")),
  ("build stickfix-bot", _has("uv", "build", "--package", "stickfix-bot")),
)
POSTGRES_SEQUENCE: tuple[tuple[str, StepPredicate], ...] = (
  ("alembic upgrade head", _has("alembic", "upgrade", "head")),
  ("alembic check", _has("alembic", "check")),
  ("pytest -m integration", _has("pytest", "-m", "integration")),
)


@pytest.mark.parametrize(
  ("job_name", "sequence"),
  [("quality", QUALITY_SEQUENCE), ("postgres-contract", POSTGRES_SEQUENCE)],
)
def test_ci_jobs_run_their_verification_steps_in_order(
  job_name: str, sequence: tuple[tuple[str, StepPredicate], ...]
) -> None:
  """Given the CI workflow, each job checks the lock before running its verification steps."""
  commands = run_commands(workflow_jobs()[job_name])
  labels = [label for label, _ in sequence]
  positions = [first_index(commands, predicate, label) for label, predicate in sequence]

  assert positions == sorted(positions), list(zip(labels, positions, strict=True))


def is_locked(job: dict[str, object], step: dict[str, object]) -> bool:
  """Return whether a uv step runs with ``--locked`` or an effective ``UV_LOCKED``."""
  locked_env = effective_env(job, step).get("UV_LOCKED", "").lower() in {"1", "true"}
  return "--locked" in step["run"].split() or locked_env


@pytest.mark.parametrize("job_name", LOCKED_JOBS)
def test_ci_project_commands_run_with_a_locked_policy(job_name: str) -> None:
  """Every ``uv run`` and ``uv sync`` in the project jobs refuses to update the lock."""
  job = workflow_jobs()[job_name]
  uv_steps = [
    step
    for step in job["steps"]
    if "run" in step and any(f"uv {verb}" in step["run"] for verb in ("run", "sync"))
  ]

  assert uv_steps
  assert [step["run"] for step in uv_steps if not is_locked(job, step)] == []


def test_ci_pins_the_approved_uv_version_in_every_job() -> None:
  """Every job that installs uv uses the single maintainer-approved release."""
  pins = {
    (name, step["with"].get("version"))
    for name, job in workflow_jobs().items()
    for step in job["steps"]
    if str(step.get("uses", "")).startswith("astral-sh/setup-uv")
  }

  assert {name for name, _ in pins} >= set(LOCKED_JOBS)
  assert {version for _, version in pins} == {UV_VERSION}


def test_postgres_job_keeps_its_database_configuration() -> None:
  """Alembic steps see the disposable database URL; integration tests see the test URL."""
  job = workflow_jobs()["postgres-contract"]
  steps = [step for step in job["steps"] if "run" in step]
  alembic = [step for step in steps if "alembic" in step["run"]]
  integration = [step for step in steps if "integration" in step["run"]]

  assert alembic and integration
  for step in alembic:
    assert effective_env(job, step)["STICKFIX_DATABASE_URL"] == DATABASE_URL
  for step in integration:
    assert effective_env(job, step)["STICKFIX_TEST_DATABASE_URL"] == DATABASE_URL
