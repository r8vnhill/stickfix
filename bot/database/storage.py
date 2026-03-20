#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Persistence adapter for the legacy YAML-backed user store.

This module defines [StickfixDB], the compatibility-facing persistence object still used by the bot
runtime and its handlers.

The store exposes mutable-mapping semantics over an in-memory `dict[str, StickfixUser]` while
persisting that mapping to a YAML file on disk. For compatibility with existing `data/<name>.yaml`
files, the current implementation preserves the legacy object-based YAML representation used by
older versions of the application.

The persistence strategy favors simplicity and recovery over partial writes:

- All entries are loaded into memory during construction or [reload].
- [save] persists the full mapping as a complete YAML snapshot.
- Before replacing the main file, the store rotates two backup files.
- Writes are performed through a temporary sibling file and finalized with an atomic `os.replace`.
- If the main file becomes unreadable, the store attempts recovery from the most recent readable
  backup.

## Notes

This module intentionally continues to use `yaml.Loader` rather than `safe_load` because the current
persisted wire format contains Python object tags for [StickfixUser]. A future migration should
replace that format with an explicit schema and safe serialization/deserialization.
"""

import os
import shutil
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import KeysView

import yaml

from bot.domain.user import StickfixUser
from bot.utils.logger import StickfixLogger

logger = StickfixLogger(__name__)


class StickfixDB(MutableMapping[str, StickfixUser]):
    """Mutable mapping backed by a YAML snapshot on disk.

    [StickfixDB] keeps the full database in memory and behaves like a standard mutable mapping from
    user identifiers to [StickfixUser] instances. Changes made through normal mapping operations
    remain in memory until [save] is called.

    The on-disk representation consists of:

    - one primary YAML file: `<data_dir>/<name>.yaml`
    - two rotating backups:
      - `<data_dir>/<name>.yaml_1.bak`
      - `<data_dir>/<name>.yaml_2.bak`

    Construction guarantees that the data directory exists and that the main YAML file is present,
    creating an empty store on first use.

    Args:
        name: Logical database name used to derive the YAML file name.
        data_dir: Directory where the database file and its backups are stored.

    Raises:
        RuntimeError: If the main YAML file is unreadable and recovery from both backup files fails.
        OSError: If the data directory or initial YAML file cannot be created.

    Example:
        ```python
        db = StickfixDB("users")
        db["alice"] = some_user
        db.save()
        ```
    """

    _name: str
    _data_dir: Path
    _yaml_path: Path
    _bak_1_path: Path
    _bak_2_path: Path
    _db: dict[str, StickfixUser]

    def __init__(self, name: str, data_dir: str | Path = "data") -> None:
        """Initializes the database and loads its current contents.

        The constructor creates the target data directory when necessary. If the main YAML file does
        not yet exist, it is initialized with an empty mapping before the in-memory database is
        loaded.

        Args:
            name: Logical database name used to derive the file path.
            data_dir: Directory where the database and backups live.
        """
        self._name = name
        self._data_dir = Path(data_dir)
        self._yaml_path = self._data_dir / f"{name}.yaml"
        self._bak_1_path = Path(f"{self._yaml_path}_1.bak")
        self._bak_2_path = Path(f"{self._yaml_path}_2.bak")
        self._db = {}

        self._data_dir.mkdir(parents=True, exist_ok=True)
        if not self._yaml_path.exists():
            self._write_yaml_file(self._yaml_path, {})
        self.reload()

    def __getitem__(self, item: str) -> StickfixUser:
        """Returns the user associated with `item`.

        Args:
            item: Key to look up in the in-memory mapping.

        Returns:
            The [StickfixUser] stored under `item`.

        Raises:
            KeyError: If `item` is not present.
        """
        return self._db[item]

    def __setitem__(self, key: str, value: StickfixUser) -> None:
        """Stores or replaces a user in the in-memory mapping.

        This operation only updates the in-memory state. Call [save] to persist the change to disk.

        Args:
            key: Mapping key to insert or replace.
            value: User value associated with `key`.
        """
        self._db[key] = value

    def __delitem__(self, key: str) -> None:
        """Removes a user from the in-memory mapping.

        This operation only updates the in-memory state. Call [save] to persist the deletion to
        disk.

        Args:
            key: Mapping key to delete.

        Raises:
            KeyError: If `key` is not present.
        """
        del self._db[key]

    def __iter__(self) -> Iterator[str]:
        """Iterates over the current in-memory keys.

        Returns:
            An iterator over database keys.
        """
        return iter(self._db)

    def __len__(self) -> int:
        """Returns the number of users currently loaded in memory.

        Returns:
            The size of the in-memory mapping.
        """
        return len(self._db)

    def get_keys(self) -> KeysView[str]:
        """Returns a live view of the current in-memory keys.

        This method is preserved for compatibility with legacy callers that expect an explicit
        key-view accessor instead of using `db.keys()`.

        Returns:
            A dynamic view over the keys of the in-memory mapping.
        """
        return self._db.keys()

    def reload(self) -> None:
        """Reloads the in-memory mapping from the disk.

        The method first attempts to load the main YAML file. If that fails due to an I/O or YAML
        parsing error, it falls back to backup-based recovery.

        Recovery tries the most recent backup first and restores the first readable backup as the
        new main database file.

        Raises:
            RuntimeError: If neither the main file nor any backup can be loaded.
        """
        try:
            self._db = self._load_path(self._yaml_path)
        except (OSError, yaml.YAMLError):
            logger.error(f"Unexpected error loading {self._yaml_path}")
            self._db = self._recover_from_backups()

    def save(self) -> None:
        """Persists the current in-memory mapping to disk.

        The save sequence is:

        1. Rotate backups so the previous snapshots remain available.
        2. Write the current mapping to a temporary sibling file.
        3. Validate that the temporary file can be loaded successfully.
        4. Atomically replace the main YAML file with the validated temp file.
        5. Reload the database from disk so the in-memory state matches the persisted state exactly.

        If validation or replacement fails, the temporary file is removed and the original exception
        is re-raised.

        Raises:
            OSError: If file creation, replacement, or cleanup fails.
            yaml.YAMLError: If the temporary YAML snapshot cannot be parsed.
            RuntimeError: If the final reload fails and backup recovery is not possible.
        """
        self._rotate_backups()
        temp_path = self._write_temp_file(self._db)
        try:
            self._load_path(temp_path)
            os.replace(temp_path, self._yaml_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        logger.debug("Database saved.")
        self.reload()

    def _recover_from_backups(self) -> dict[str, StickfixUser]:
        """Recovers the database from the first readable backup.

        Backups are tried in recency order: first backup 1, then backup 2. When a readable backup is
        found, it is copied back into the main YAML path and returned as the new in-memory state.

        Returns:
            The recovered database mapping.

        Raises:
            RuntimeError: If no readable backup is available.
        """
        for backup_path in (self._bak_1_path, self._bak_2_path):
            try:
                logger.debug(f"Loading {backup_path}")
                db = self._load_path(backup_path)
                shutil.copy2(backup_path, self._yaml_path)
                return db
            except (OSError, yaml.YAMLError):
                logger.error(f"Unexpected error loading {backup_path}")
        raise RuntimeError(f"Could not recover database from backups for {self._yaml_path}")

    def _rotate_backups(self) -> None:
        """Rotates the two backup snapshots.

        The rotation strategy preserves the two most recent previously persisted states:

        - backup 1 is copied to backup 2
        - the current main YAML file is copied to backup 1

        Missing files are ignored, which allows the same logic to work during the first few saves of
        a newly created database.
        """
        if self._bak_1_path.exists():
            shutil.copy2(self._bak_1_path, self._bak_2_path)
        if self._yaml_path.exists():
            shutil.copy2(self._yaml_path, self._bak_1_path)

    def _write_temp_file(self, data: dict[str, StickfixUser]) -> Path:
        """Writes a full YAML snapshot to a temporary sibling file.

        Writing to a temporary file in the same directory allows the final `os.replace` to remain
        atomic on the target filesystem.

        Args:
            data: Full in-memory mapping to serialize.

        Returns:
            The path to the newly written temporary file.

        Raises:
            OSError: If the temporary file cannot be created or written.
        """
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self._data_dir,
            delete=False,
        ) as handle:
            yaml.dump(data, handle, yaml.Dumper)
            return Path(handle.name)

    @staticmethod
    def _write_yaml_file(path: Path, data: dict[str, StickfixUser]) -> None:
        """Writes a full YAML snapshot directly to `path`.

        This helper is currently used for first-time initialization when the main database file does
        not yet exist.

        Args:
            path: Destination YAML file path.
            data: Mapping to serialize.

        Raises:
            OSError: If `path` cannot be opened or written.
        """
        with path.open("w", encoding="utf-8") as handle:
            yaml.dump(data, handle, yaml.Dumper)

    @staticmethod
    def _load_path(path: Path) -> dict[str, StickfixUser]:
        """Loads one YAML snapshot from the disk.

        The current legacy persistence format stores Python object tags for [StickfixUser], so this
        method uses `yaml.Loader` for compatibility. An empty YAML document is normalized to an
        empty mapping.

        Args:
            path: YAML file to load.

        Returns:
            The parsed mapping is stored in `path`, or an empty mapping if the file is empty.

        Raises:
            OSError: If the file cannot be opened.
            yaml.YAMLError: If the file contents are not valid YAML.
        """
        with path.open("r", encoding="utf-8") as handle:
            # The current persisted YAML uses Python object tags for StickfixUser.
            data = yaml.load(handle, yaml.Loader)  # noqa: S506
        if data is None:
            return {}
        return data
