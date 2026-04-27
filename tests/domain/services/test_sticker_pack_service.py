from __future__ import annotations

from hamcrest import assert_that, equal_to, is_, same_instance

from bot.domain.services import StickerPackService
from bot.domain.user import SF_PUBLIC, StickfixUser


def test_resolves_public_pack_for_public_mode_user() -> None:
    user = StickfixUser("alice")
    public_pack = StickfixUser(SF_PUBLIC)

    effective_pack = StickerPackService().resolve_effective_pack(user, public_pack)

    assert_that(effective_pack, same_instance(public_pack))


def test_resolves_private_pack_for_private_mode_user() -> None:
    user = StickfixUser("alice")
    user.private_mode = True
    public_pack = StickfixUser(SF_PUBLIC)

    effective_pack = StickerPackService().resolve_effective_pack(user, public_pack)

    assert_that(effective_pack, same_instance(user))


def test_add_sticker_mutates_effective_public_pack() -> None:
    user = StickfixUser("alice")
    public_pack = StickfixUser(SF_PUBLIC)

    mutation = StickerPackService().add_sticker(user, "sticker-1", ("wave",), public_pack)

    assert_that(mutation.effective_pack, same_instance(public_pack))
    assert_that(mutation.changed, is_(True))
    assert_that(user.stickers, equal_to({}))
    assert_that(public_pack.stickers, equal_to({"wave": ["sticker-1"]}))


def test_add_sticker_with_empty_tags_is_noop() -> None:
    user = StickfixUser("alice")
    public_pack = StickfixUser(SF_PUBLIC)

    mutation = StickerPackService().add_sticker(user, "sticker-1", (), public_pack)

    assert_that(mutation.effective_pack, same_instance(public_pack))
    assert_that(mutation.changed, is_(False))
    assert_that(user.stickers, equal_to({}))
    assert_that(public_pack.stickers, equal_to({}))


def test_delete_sticker_mutates_effective_private_pack() -> None:
    user = StickfixUser("alice")
    user.private_mode = True
    user.add_sticker("sticker-1", ["wave"])
    public_pack = StickfixUser(SF_PUBLIC)

    mutation = StickerPackService().delete_sticker(user, "sticker-1", ("wave",), public_pack)

    assert_that(mutation.effective_pack, same_instance(user))
    assert_that(mutation.changed, is_(True))
    assert_that(user.stickers, equal_to({}))


def test_find_stickers_preserves_domain_lookup_behavior() -> None:
    user = StickfixUser("alice")
    public_pack = StickfixUser(SF_PUBLIC)
    user.add_sticker("private", ["wave"])
    public_pack.add_sticker("public", ["wave"])

    sticker_ids = StickerPackService().find_stickers(user, ("wave",), public_pack)

    assert_that(set(sticker_ids), equal_to({"private", "public"}))
