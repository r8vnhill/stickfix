from __future__ import annotations

import pytest
from hamcrest import assert_that, equal_to, is_

from bot.application.errors import MissingStickerError, WrongInteractionContextError
from bot.application.requests import AddStickerCommand, DeleteStickerCommand, GetStickersQuery
from bot.application.use_cases import AddSticker, DeleteSticker, GetStickers
from bot.domain.user import SF_PUBLIC, StickfixUser


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, StickfixUser] = {}
        self.saved_users: list[StickfixUser] = []

    def get_user(self, user_id: str) -> StickfixUser | None:
        return self.users.get(user_id)

    def has_user(self, user_id: str) -> bool:
        return user_id in self.users

    def save_user(self, user: StickfixUser) -> None:
        self.users[user.id] = user
        self.saved_users.append(user)

    def delete_user(self, user_id: str) -> bool:
        return self.users.pop(user_id, None) is not None

    def get_public_pack(self) -> StickfixUser | None:
        return self.get_user(SF_PUBLIC)

    def ensure_public_pack(self) -> StickfixUser:
        public_pack = self.get_public_pack()
        if public_pack is None:
            public_pack = StickfixUser(SF_PUBLIC)
            self.save_user(public_pack)
        return public_pack


def add_command(**overrides) -> AddStickerCommand:
    values = {
        "user_id": "alice",
        "chat_id": "chat-1",
        "chat_type": "private",
        "reply_sticker_id": "sticker-1",
        "reply_sticker_emoji": "smile",
        "tags": ("wave",),
    }
    values.update(overrides)
    return AddStickerCommand(**values)


def test_add_sticker_creates_and_uses_public_pack_by_default() -> None:
    repository = FakeUserRepository()

    result = AddSticker(repository)(add_command())

    assert_that(result.changed, is_(True))
    assert_that(repository.users[SF_PUBLIC].stickers, equal_to({"wave": ["sticker-1"]}))


def test_add_sticker_writes_to_private_pack_when_private_mode_is_enabled() -> None:
    repository = FakeUserRepository()
    user = StickfixUser("alice")
    user.private_mode = True
    repository.users["alice"] = user

    AddSticker(repository)(add_command(tags=("private",)))

    assert_that(repository.users["alice"].stickers, equal_to({"private": ["sticker-1"]}))
    assert_that(repository.users[SF_PUBLIC].stickers, equal_to({}))


def test_add_sticker_falls_back_to_emoji_when_tags_are_absent() -> None:
    repository = FakeUserRepository()

    result = AddSticker(repository)(add_command(tags=()))

    assert_that(result.effective_tags, equal_to(("smile",)))
    assert_that(repository.users[SF_PUBLIC].stickers, equal_to({"smile": ["sticker-1"]}))


def test_add_sticker_with_no_tags_and_no_emoji_keeps_noop_success() -> None:
    repository = FakeUserRepository()

    result = AddSticker(repository)(add_command(tags=(), reply_sticker_emoji=None))

    assert_that(result.changed, is_(False))
    assert_that(result.effective_tags, equal_to(()))
    assert_that(repository.users[SF_PUBLIC].stickers, equal_to({}))


def test_add_sticker_rejects_missing_sticker_id() -> None:
    repository = FakeUserRepository()

    with pytest.raises(MissingStickerError):
        AddSticker(repository)(add_command(reply_sticker_id=None))


def test_get_stickers_rejects_non_private_chats() -> None:
    repository = FakeUserRepository()

    with pytest.raises(WrongInteractionContextError):
        GetStickers(repository)(
            GetStickersQuery(user_id="alice", chat_id="chat-1", chat_type="group", tags=("wave",))
        )


def test_get_stickers_falls_back_to_public_pack_for_missing_user() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("public", ["wave"])

    result = GetStickers(repository)(
        GetStickersQuery(user_id="alice", chat_id="chat-1", chat_type="private", tags=("wave",))
    )

    assert_that(result.sticker_ids, equal_to(("public",)))


def test_get_stickers_uses_private_user_pack_when_private_mode_is_enabled() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("public", ["wave"])
    user = StickfixUser("alice")
    user.private_mode = True
    user.add_sticker("private", ["wave"])
    repository.users["alice"] = user

    result = GetStickers(repository)(
        GetStickersQuery(user_id="alice", chat_id="chat-1", chat_type="private", tags=("wave",))
    )

    assert_that(result.sticker_ids, equal_to(("private",)))


def test_delete_sticker_removes_from_public_pack_by_default() -> None:
    repository = FakeUserRepository()
    public_pack = repository.ensure_public_pack()
    public_pack.add_sticker("sticker-1", ["wave"])

    result = DeleteSticker(repository)(
        DeleteStickerCommand(
            user_id="alice",
            chat_id="chat-1",
            chat_type="private",
            reply_sticker_id="sticker-1",
            tags=("wave",),
        )
    )

    assert_that(result.changed, is_(True))
    assert_that(repository.users[SF_PUBLIC].stickers, equal_to({}))


def test_delete_sticker_removes_from_private_pack_when_private_mode_is_enabled() -> None:
    repository = FakeUserRepository()
    repository.ensure_public_pack()
    user = StickfixUser("alice")
    user.private_mode = True
    user.add_sticker("sticker-1", ["wave"])
    repository.users["alice"] = user

    DeleteSticker(repository)(
        DeleteStickerCommand(
            user_id="alice",
            chat_id="chat-1",
            chat_type="private",
            reply_sticker_id="sticker-1",
            tags=("wave",),
        )
    )

    assert_that(repository.users["alice"].stickers, equal_to({}))
