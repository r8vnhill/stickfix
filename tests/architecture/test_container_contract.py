"""Static Dockerfile, Compose, and container-CI contracts (Phase D.2).

The image must contain every source the root distribution builds from, install the locked
runtime-only environment, and then stop ``uv run`` from re-syncing at startup, while the existing
``CMD`` and Compose commands stay unchanged until Milestone 4.6 changes them deliberately.

These checks are fast and run everywhere; the real ``docker build`` and the offline
``container_smoke.py`` probe run in the ``container`` CI job, which these tests also pin. The
Dockerfile reader handles only the syntax this repository uses (continuations, comments, shell- and
JSON-form instructions); it is not a general Dockerfile parser.
"""

from __future__ import annotations

import ast
import json
import shlex
import sys
from dataclasses import dataclass

import yaml
from ci_workflow_support import run_commands, workflow_jobs
from package_contract_support import ROOT, UV_VERSION, project_metadata

DEFAULT_CMD = ["uv", "run", "python", "-m", "bot"]
MIGRATE_COMMAND = ["uv", "run", "alembic", "upgrade", "head"]
# Sources setuptools reads for the root wheel; py-modules are added from pyproject.toml.
BUILD_INPUTS = {
  "pyproject.toml",
  "uv.lock",
  "README.md",
  "packages",
  "bot",
  "alembic.ini",
  "alembic",
}
DEV_SELECTIONS = {"--dev", "--all-groups", "--group", "--only-dev", "--only-group"}
SMOKE_PROBE = ROOT / "tests" / "architecture" / "container_smoke.py"


@dataclass(frozen=True)
class Instruction:
  """One Dockerfile instruction with its continuation lines joined."""

  keyword: str
  arguments: str


def dockerfile_instructions() -> list[Instruction]:
  """Split the Dockerfile into instructions, joining continuations and skipping comments."""
  instructions: list[Instruction] = []
  pending = ""
  for raw in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
      continue
    if line.endswith("\\"):
      pending += line[:-1] + " "
      continue
    keyword, _, arguments = (pending + line).partition(" ")
    instructions.append(Instruction(keyword.upper(), arguments.strip()))
    pending = ""
  return instructions


def index_of(instructions: list[Instruction], keyword: str, fragment: str) -> int:
  """Return the position of the first ``keyword`` instruction containing ``fragment``."""
  for index, instruction in enumerate(instructions):
    if instruction.keyword == keyword and fragment in instruction.arguments:
      return index
  raise AssertionError(f"Dockerfile has no {keyword} containing {fragment!r}")


def copy_sources(instruction: Instruction) -> list[str]:
  """Return the normalized sources of a shell-form or JSON-form COPY instruction."""
  arguments = instruction.arguments
  if arguments.startswith("["):
    tokens = json.loads(arguments)
  else:
    tokens = [token for token in shlex.split(arguments) if not token.startswith("--")]
  return [source.removeprefix("./").rstrip("/") for source in tokens[:-1]]


def env_settings(instruction: Instruction) -> dict[str, str]:
  """Parse a ``key=value`` ENV instruction."""
  return dict(token.split("=", 1) for token in shlex.split(instruction.arguments))


def required_build_inputs() -> set[str]:
  """Return every file or directory the root distribution needs in the build context."""
  py_modules = project_metadata()["tool"]["setuptools"].get("py-modules", [])
  return BUILD_INPUTS | {f"{module}.py" for module in py_modules}


def test_dockerfile_copies_every_build_input_before_the_locked_sync() -> None:
  """Given the root distribution's sources, the image copies them all before installing."""
  instructions = dockerfile_instructions()
  sync = index_of(instructions, "RUN", "uv sync")
  copied = {
    source
    for instruction in instructions[:sync]
    if instruction.keyword == "COPY"
    for source in copy_sources(instruction)
  }

  assert required_build_inputs() - copied == set()


def test_dockerfile_installs_the_locked_runtime_only_environment() -> None:
  """The image validates the lockfile and never selects the development group."""
  instructions = dockerfile_instructions()
  sync = shlex.split(instructions[index_of(instructions, "RUN", "uv sync")].arguments)

  assert "--locked" in sync
  assert "--no-dev" in sync
  assert "--frozen" not in sync
  assert not DEV_SELECTIONS & set(sync)


def test_dockerfile_pins_the_approved_uv_version() -> None:
  """The image installs the same uv release as CI."""
  instructions = dockerfile_instructions()

  assert f"uv=={UV_VERSION}" in instructions[index_of(instructions, "RUN", "uv==")].arguments


def test_dockerfile_disables_runtime_sync_only_after_installing() -> None:
  """``UV_NO_SYNC=1`` follows the build-time sync, so only runtime ``uv run`` skips syncing."""
  instructions = dockerfile_instructions()
  sync = index_of(instructions, "RUN", "uv sync")
  no_sync = [
    index
    for index, instruction in enumerate(instructions)
    if instruction.keyword == "ENV" and env_settings(instruction).get("UV_NO_SYNC") == "1"
  ]

  assert no_sync, "Dockerfile never sets UV_NO_SYNC=1"
  assert min(no_sync) > sync


def test_dockerfile_keeps_the_existing_default_command() -> None:
  """The startup command stays unchanged until Milestone 4.6 changes it deliberately."""
  commands = [item for item in dockerfile_instructions() if item.keyword == "CMD"]

  assert len(commands) == 1
  assert json.loads(commands[0].arguments) == DEFAULT_CMD


# --- Compose ----------------------------------------------------------------------------------


def compose_services() -> dict[str, dict[str, object]]:
  """Return the Compose services, with YAML anchors and merge keys resolved."""
  compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
  return compose["services"]


def test_compose_bot_and_migrate_share_the_image_and_entrypoints() -> None:
  """Given the Compose services, bot and migrate keep the same image and commands."""
  services = compose_services()
  bot, migrate = services["bot"], services["migrate"]

  assert bot["build"] == "." and migrate["build"] == "."
  assert migrate["command"] == MIGRATE_COMMAND
  assert "command" not in bot and "entrypoint" not in bot
  assert migrate["depends_on"]["db"]["condition"] == "service_healthy"
  assert bot["depends_on"]["migrate"]["condition"] == "service_completed_successfully"


def test_compose_services_share_the_database_url() -> None:
  """Both services receive the same interpolated psycopg URL for the db service."""
  services = compose_services()
  urls = {services[name]["environment"]["STICKFIX_DATABASE_URL"] for name in ("bot", "migrate")}

  assert len(urls) == 1
  (url,) = urls
  assert url.startswith("postgresql+psycopg://") and "@db:5432/" in url


# --- Container CI job and smoke probe ---------------------------------------------------------


def test_container_ci_job_builds_and_probes_the_image_offline() -> None:
  """The container job builds the image, probes it offline, and checks its configuration."""
  commands = " && ".join(run_commands(workflow_jobs()["container"]))

  assert "docker build" in commands
  assert "--network none" in commands and "UV_OFFLINE=1" in commands
  assert SMOKE_PROBE.relative_to(ROOT).as_posix() in commands
  assert "alembic --version" in commands
  assert "docker image inspect" in commands and "UV_NO_SYNC=1" in commands
  assert json.dumps(DEFAULT_CMD, separators=(",", ":")) in commands
  assert "docker compose config --quiet" in commands


def imported_top_level_modules(source: str) -> set[str]:
  """Return the top-level names of every absolute import in a Python source."""
  imported: set[str] = set()
  for node in ast.walk(ast.parse(source)):
    if isinstance(node, ast.Import):
      imported |= {alias.name.partition(".")[0] for alias in node.names}
    elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
      imported.add(node.module.partition(".")[0])
  return imported


def test_container_smoke_probe_uses_only_the_standard_library() -> None:
  """The probe runs inside the image without test-framework or project-tooling imports."""
  imported = imported_top_level_modules(SMOKE_PROBE.read_text(encoding="utf-8"))

  assert imported <= sys.stdlib_module_names, imported - sys.stdlib_module_names
