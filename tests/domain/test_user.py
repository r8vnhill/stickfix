from unittest.mock import patch

from bot.domain.user import SF_PUBLIC, StickfixUser


def test_add_sticker_sorts_and_deduplicates_ids_per_tag():
    user = StickfixUser("user-1")

    user.add_sticker("sticker-b", ["wave", "hello"])
    user.add_sticker("sticker-a", ["wave"])
    user.add_sticker("sticker-a", ["wave"])

    assert user.stickers["wave"] == ["sticker-a", "sticker-b"]
    assert user.stickers["hello"] == ["sticker-b"]


def test_link_and_unlink_use_public_pack_when_user_is_not_private():
    user = StickfixUser("user-1")
    public_user = StickfixUser(SF_PUBLIC)

    user.link_sticker("sticker-1", ["wave"], public_user=public_user)

    assert user.stickers == {}
    assert public_user.stickers == {"wave": ["sticker-1"]}

    user.unlink_sticker_from_pack("sticker-1", ["wave"], public_user=public_user)

    assert public_user.stickers == {}


def test_link_and_unlink_use_private_pack_when_private_mode_is_enabled():
    user = StickfixUser("user-1")
    user.private_mode = True
    public_user = StickfixUser(SF_PUBLIC)

    user.link_sticker("sticker-1", ["wave"], public_user=public_user)

    assert user.stickers == {"wave": ["sticker-1"]}
    assert public_user.stickers == {}

    user.unlink_sticker_from_pack("sticker-1", ["wave"], public_user=public_user)

    assert user.stickers == {}


def test_get_stickers_prefers_cached_values_until_cache_is_cleared():
    user = StickfixUser("user-1")
    user.add_sticker("stored-sticker", ["wave"])
    user.cache["wave"] = ["cached-sticker"]

    assert user.get_stickers("wave") == {"cached-sticker"}

    user.remove_cached_stickers()

    assert user.get_stickers("wave") == {"stored-sticker"}


def test_resolve_sticker_list_caches_per_tag_and_intersects_matches():
    user = StickfixUser("user-1")
    public_user = StickfixUser(SF_PUBLIC)

    user.add_sticker("private-only", ["wave"])
    user.add_sticker("shared-private", ["wave", "smile"])
    public_user.add_sticker("shared-public", ["wave", "smile"])
    public_user.add_sticker("public-only", ["smile"])

    stickers = user.resolve_sticker_list(["wave", "smile"], public_user=public_user)

    assert set(stickers) == {"shared-private", "shared-public"}
    assert set(user.cache["wave"]) == {"private-only", "shared-private", "shared-public"}
    assert set(user.cache["smile"]) == {"shared-private", "shared-public", "public-only"}


def test_resolve_sticker_list_uses_only_private_pack_in_private_mode():
    user = StickfixUser("user-1")
    user.private_mode = True
    public_user = StickfixUser(SF_PUBLIC)

    user.add_sticker("private-shared", ["wave", "smile"])
    public_user.add_sticker("public-shared", ["wave", "smile"])

    stickers = user.resolve_sticker_list(["wave", "smile"], public_user=public_user)

    assert stickers == ["private-shared"]
    assert user.cache["wave"] == ["private-shared"]
    assert user.cache["smile"] == ["private-shared"]


def test_random_tag_returns_empty_or_single_known_tag():
    empty_user = StickfixUser("empty")

    assert empty_user.random_tag() == []

    user = StickfixUser("user-1")
    user.add_sticker("sticker-1", ["wave"])
    user.add_sticker("sticker-2", ["smile"])

    random_tag = user.random_tag()

    assert len(random_tag) == 1
    assert random_tag[0] in {"wave", "smile"}


def test_get_shuffled_sticker_list_only_changes_order():
    user = StickfixUser("user-1")
    user.shuffle = True
    public_user = StickfixUser(SF_PUBLIC)
    user.add_sticker("b", ["wave"])
    user.add_sticker("a", ["wave"])
    public_user.add_sticker("c", ["wave"])

    def reverse_in_place(values):
        values.reverse()

    with patch("bot.domain.user.random.shuffle", side_effect=reverse_in_place) as shuffle:
        stickers = user.get_shuffled_sticker_list(["wave"], public_user=public_user)

    assert set(stickers) == {"a", "b", "c"}
    shuffle.assert_called_once()
