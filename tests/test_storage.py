from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from bot.database.storage import StickfixDB
from bot.domain.user import StickfixUser


def create_user(user_id: str, *, private_mode: bool = False, shuffle: bool = False) -> StickfixUser:
    user = StickfixUser(user_id)
    user.private_mode = private_mode
    user.shuffle = shuffle
    user.add_sticker(f"{user_id}-sticker", ["wave"])
    return user


def dump_store(path: Path, data: dict[str, StickfixUser]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle, yaml.Dumper)


def test_init_creates_missing_directory_and_file(tmp_path):
    data_dir = tmp_path / "missing-data"

    store = StickfixDB("users", data_dir=data_dir)

    assert data_dir.exists()
    assert (data_dir / "users.yaml").exists()
    assert len(store) == 0


def test_init_creates_missing_yaml_file_when_directory_exists(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    store = StickfixDB("users", data_dir=data_dir)

    assert (data_dir / "users.yaml").exists()
    assert len(store) == 0


def test_empty_yaml_loads_as_empty_store(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "users.yaml").write_text("", encoding="utf-8")

    store = StickfixDB("users", data_dir=data_dir)

    assert len(store) == 0
    assert dict(store) == {}


def test_store_behaves_like_a_mapping(tmp_path):
    store = StickfixDB("users", data_dir=tmp_path)
    alice = create_user("alice")
    bob = create_user("bob")

    store["alice"] = alice
    store["bob"] = bob

    assert "alice" in store
    assert len(store) == 2
    assert list(iter(store)) == ["alice", "bob"]
    assert dict(store) == {"alice": alice, "bob": bob}
    assert list(store.get_keys()) == ["alice", "bob"]

    del store["alice"]

    assert "alice" not in store
    assert dict(store) == {"bob": bob}


def test_save_load_roundtrip_and_overwrite_preserve_logical_contents(tmp_path):
    store = StickfixDB("users", data_dir=tmp_path)
    original = create_user("alice")
    replacement = create_user("alice", private_mode=True, shuffle=True)

    store["alice"] = original
    store.save()
    store["alice"] = replacement
    store.save()

    reloaded = StickfixDB("users", data_dir=tmp_path)

    assert set(reloaded.get_keys()) == {"alice"}
    assert reloaded["alice"].private_mode is True
    assert reloaded["alice"].shuffle is True
    assert reloaded["alice"].stickers == replacement.stickers


def test_save_rotates_backups_in_order(tmp_path):
    store = StickfixDB("users", data_dir=tmp_path)
    yaml_path = tmp_path / "users.yaml"
    bak1 = tmp_path / "users.yaml_1.bak"
    bak2 = tmp_path / "users.yaml_2.bak"

    store["first"] = create_user("first")
    store.save()
    first_contents = yaml_path.read_text(encoding="utf-8")

    store["second"] = create_user("second")
    store.save()
    second_contents = yaml_path.read_text(encoding="utf-8")

    store["third"] = create_user("third")
    store.save()

    assert bak1.exists()
    assert bak2.exists()
    assert bak1.read_text(encoding="utf-8") == second_contents
    assert bak2.read_text(encoding="utf-8") == first_contents


def test_load_recovers_from_backup_one_when_main_yaml_is_corrupted(tmp_path):
    yaml_path = tmp_path / "users.yaml"
    bak1 = tmp_path / "users.yaml_1.bak"
    expected = {"alice": create_user("alice")}

    dump_store(yaml_path, {})
    dump_store(bak1, expected)
    yaml_path.write_text("invalid: [yaml", encoding="utf-8")

    store = StickfixDB("users", data_dir=tmp_path)

    assert set(store.get_keys()) == {"alice"}
    assert store["alice"].stickers == expected["alice"].stickers
    assert yaml_path.read_text(encoding="utf-8") == bak1.read_text(encoding="utf-8")


def test_load_recovers_from_backup_two_when_main_and_backup_one_fail(tmp_path):
    yaml_path = tmp_path / "users.yaml"
    bak1 = tmp_path / "users.yaml_1.bak"
    bak2 = tmp_path / "users.yaml_2.bak"
    expected = {"alice": create_user("alice")}

    yaml_path.write_text("invalid: [yaml", encoding="utf-8")
    bak1.write_text("invalid: [yaml", encoding="utf-8")
    dump_store(bak2, expected)

    store = StickfixDB("users", data_dir=tmp_path)

    assert set(store.get_keys()) == {"alice"}
    assert store["alice"].stickers == expected["alice"].stickers
    assert yaml_path.read_text(encoding="utf-8") == bak2.read_text(encoding="utf-8")


def test_load_recovers_from_backup_when_main_read_raises_oserror(tmp_path):
    yaml_path = tmp_path / "users.yaml"
    bak1 = tmp_path / "users.yaml_1.bak"
    expected = {"alice": create_user("alice")}

    dump_store(yaml_path, {})
    dump_store(bak1, expected)

    original_open = Path.open

    def flaky_open(path_obj, *args, **kwargs):
        if path_obj == yaml_path:
            raise OSError("main file unavailable")
        return original_open(path_obj, *args, **kwargs)

    with patch("pathlib.Path.open", autospec=True, side_effect=flaky_open):
        store = StickfixDB("users", data_dir=tmp_path)

    assert set(store.get_keys()) == {"alice"}
    assert store["alice"].stickers == expected["alice"].stickers


def test_save_is_atomic_when_replace_fails(tmp_path):
    store = StickfixDB("users", data_dir=tmp_path)
    yaml_path = tmp_path / "users.yaml"
    store["first"] = create_user("first")
    store.save()
    original_contents = yaml_path.read_text(encoding="utf-8")

    store["second"] = create_user("second")

    with patch("bot.database.storage.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(OSError):
            store.save()

    assert yaml_path.read_text(encoding="utf-8") == original_contents
    reloaded = StickfixDB("users", data_dir=tmp_path)
    assert set(reloaded.get_keys()) == {"first"}


def test_save_is_atomic_when_temp_validation_fails(tmp_path):
    store = StickfixDB("users", data_dir=tmp_path)
    yaml_path = tmp_path / "users.yaml"
    store["first"] = create_user("first")
    store.save()
    original_contents = yaml_path.read_text(encoding="utf-8")

    store["second"] = create_user("second")
    original_validate = StickfixDB._load_path

    def broken_validate(self, path):
        if path != self._yaml_path:
            raise yaml.YAMLError("temp validation failed")
        return original_validate(self, path)

    with patch.object(StickfixDB, "_load_path", broken_validate):
        with pytest.raises(yaml.YAMLError):
            store.save()

    assert yaml_path.read_text(encoding="utf-8") == original_contents
    reloaded = StickfixDB("users", data_dir=tmp_path)
    assert set(reloaded.get_keys()) == {"first"}
