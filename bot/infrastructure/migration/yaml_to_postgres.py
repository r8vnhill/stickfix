"""Import a historical ``users.yaml`` into PostgreSQL with all-or-nothing validation.

Run as a module: ``python -m bot.infrastructure.migration.yaml_to_postgres --source
<path> (--dry-run | --apply)``. The target database URL comes from
``STICKFIX_DATABASE_URL`` (never a CLI argument). ``--dry-run`` only reports the
source digest and expected counts; ``--apply`` imports through the migration-only
PostgreSQL gateway (one transaction, requires an empty database), then re-reads
PostgreSQL and fails unless its logical snapshot matches the YAML snapshot byte for
byte. A successful apply writes ``migration-receipt.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Sequence

from bot.infrastructure.migration.legacy_yaml import LegacyYamlError, load_legacy_yaml
from bot.infrastructure.migration.logical_snapshot import snapshot_from_legacy
from bot.infrastructure.migration.postgres_gateway import PostgresMigrationGateway
from bot.infrastructure.persistence.postgres import create_engine_and_session_factory


def migrate(
  source: Path,
  gateway: PostgresMigrationGateway,
  *,
  apply: bool,
  receipt_path: Path | None = None,
) -> dict[str, object]:
  """Validate ``source`` and, when ``apply`` is set, import it transactionally.

  Returns a summary dict (also written to ``receipt_path`` on a successful apply).
  Raises ``RuntimeError`` if the post-import PostgreSQL snapshot differs from the
  YAML snapshot. Source validation completes before the gateway mutates PostgreSQL.
  """
  users = load_legacy_yaml(source)
  expected = snapshot_from_legacy(users)
  summary = _base_summary(source, expected, apply)
  if not apply:
    return summary

  _import_and_verify(gateway, expected)
  summary.update(_apply_counts(expected))
  _write_receipt(receipt_path, summary)
  return summary


def _base_summary(source: Path, expected, apply: bool) -> dict[str, object]:
  return {
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "user_count": len(expected.users),
    "logical_snapshot_sha256": expected.sha256(),
    "dry_run": not apply,
  }


def _write_receipt(receipt_path: Path | None, summary: dict[str, object]) -> None:
  if receipt_path is not None:
    receipt_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _import_and_verify(
  gateway: PostgresMigrationGateway,
  expected,
) -> None:
  gateway.import_snapshot(expected)
  if gateway.read_snapshot().as_dict() != expected.as_dict():
    raise RuntimeError("PostgreSQL logical snapshot differs from YAML snapshot")


def _apply_counts(snapshot) -> dict[str, object]:
  """Receipt fields that only make sense once the import has been verified."""
  associations = _all_associations(snapshot)
  return {
    "schema_revision": "0001_initial",
    "tag_count": len({item["tag"] for item in associations}),
    "sticker_association_count": _field_count(snapshot, "stickers"),
    "cache_entry_count": _field_count(snapshot, "cached_stickers"),
  }


def _field_count(snapshot, field: str) -> int:
  return sum(len(getattr(user, field)) for user in snapshot.users) + len(
    getattr(snapshot.public_pack, field)
  )


def _all_associations(snapshot) -> list[dict[str, object]]:
  groups = [user.stickers + user.cached_stickers for user in snapshot.users]
  groups.append(snapshot.public_pack.stickers + snapshot.public_pack.cached_stickers)
  return [association.as_dict() for group in groups for association in group]


def main(argv: Sequence[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--source", type=Path, required=True)
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--apply", action="store_true")
  parser.add_argument("--receipt", type=Path, default=Path("migration-receipt.json"))
  args = parser.parse_args(argv)
  if args.dry_run == args.apply:
    parser.error("choose exactly one of --dry-run or --apply")
  gateway = _gateway_from_environment(parser)
  try:
    result = migrate(
      args.source,
      gateway,
      apply=args.apply,
      receipt_path=args.receipt if args.apply else None,
    )
  except (LegacyYamlError, ValueError, RuntimeError) as error:
    parser.error(str(error))
  print(json.dumps(result, indent=2, sort_keys=True))
  return 0


def _gateway_from_environment(parser: argparse.ArgumentParser) -> PostgresMigrationGateway:
  database_url = os.environ.get("STICKFIX_DATABASE_URL", "").strip()
  if not database_url:
    parser.error("STICKFIX_DATABASE_URL must be configured")
  _, session_factory = create_engine_and_session_factory(database_url)
  return PostgresMigrationGateway(session_factory)


if __name__ == "__main__":
  raise SystemExit(main())
