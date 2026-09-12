from __future__ import annotations

import logging

import pytest
from hamcrest import assert_that, equal_to, is_
from stickfix_domain import StickfixUser, UserId

from bot.application.errors import MissingStickerError, WrongInteractionContextError
from bot.application.requests import (
  AddStickerCommand,
  DeleteStickerCommand,
  GetStickersQuery,
  InteractionScope,
)
from bot.application.use_cases import AddSticker, DeleteSticker, GetStickers
from tests.support.repositories import InMemoryPublicPackRepository, InMemoryUserRepository


def make_command(**overrides: object) -> AddStickerCommand:
  values: dict[str, object] = {
    "user_id": UserId(1),
    "reply_sticker_id": "sticker-1",
    "reply_sticker_emoji": "smile",
    "tags": ("wave",),
  }
  values.update(overrides)
  return AddStickerCommand(**values)


def test_add_sticker_uses_public_pack_port_by_default(caplog: pytest.LogCaptureFixture) -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()

  with caplog.at_level(logging.INFO, logger="bot.application.use_cases.add_sticker"):
    result = AddSticker(users, public)(make_command())

  assert_that(result.changed, is_(True))
  assert_that(public.pack.stickers, equal_to({"wave": ["sticker-1"]}))
  assert_that(users.saved_users, equal_to([]))
  assert_that(caplog.messages, equal_to(["Sticker added to public-pack pack with tags: wave"]))


def test_add_sticker_writes_to_private_pack_when_private_mode_is_enabled() -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()
  user = StickfixUser(UserId(1))
  user.private_mode = True
  users.save_user(user)
  users.saved_users.clear()

  AddSticker(users, public)(make_command(tags=("private",)))

  assert_that(user.stickers, equal_to({"private": ["sticker-1"]}))
  assert_that(public.pack.stickers, equal_to({}))


def test_add_sticker_falls_back_to_emoji_when_tags_are_absent() -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()

  result = AddSticker(users, public)(make_command(tags=()))

  assert_that(result.effective_tags, equal_to(("smile",)))
  assert_that(public.pack.stickers, equal_to({"smile": ["sticker-1"]}))


def test_add_sticker_with_no_tags_and_no_emoji_keeps_noop_success() -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()

  result = AddSticker(users, public)(make_command(tags=(), reply_sticker_emoji=None))

  assert_that(result.changed, is_(False))
  assert_that(result.effective_tags, equal_to(()))
  assert_that(public.pack.stickers, equal_to({}))
  assert_that(public.saved_packs, equal_to([]))


def test_add_sticker_rejects_missing_sticker_id() -> None:
  with pytest.raises(MissingStickerError):
    AddSticker(InMemoryUserRepository(), InMemoryPublicPackRepository())(
      make_command(reply_sticker_id=None)
    )


def test_get_stickers_rejects_non_private_interactions() -> None:
  with pytest.raises(WrongInteractionContextError):
    GetStickers(InMemoryUserRepository(), InMemoryPublicPackRepository())(
      GetStickersQuery(
        user_id=UserId(1),
        interaction_scope=InteractionScope.NON_PRIVATE,
        tags=("wave",),
      )
    )


def test_get_stickers_falls_back_to_public_pack_for_missing_user() -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()
  public_pack = public.ensure()
  public_pack.add_sticker("public", ["wave"])

  result = GetStickers(users, public)(
    GetStickersQuery(UserId(1), InteractionScope.PRIVATE, ("wave",))
  )

  assert_that(result.sticker_ids, equal_to(("public",)))


def test_get_stickers_uses_private_user_pack_when_private_mode_is_enabled() -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()
  public_pack = public.ensure()
  public_pack.add_sticker("public", ["wave"])
  user = StickfixUser(UserId(1))
  user.private_mode = True
  user.add_sticker("private", ["wave"])
  users.save_user(user)
  users.saved_users.clear()

  result = GetStickers(users, public)(
    GetStickersQuery(UserId(1), InteractionScope.PRIVATE, ("wave",))
  )

  assert_that(result.sticker_ids, equal_to(("private",)))


def test_delete_sticker_removes_from_public_pack_by_default(
  caplog: pytest.LogCaptureFixture,
) -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()
  public_pack = public.ensure()
  public_pack.add_sticker("sticker-1", ["wave"])
  public.save(public_pack)
  public.saved_packs.clear()

  with caplog.at_level(logging.INFO, logger="bot.application.use_cases.delete_sticker"):
    result = DeleteSticker(users, public)(DeleteStickerCommand(UserId(1), "sticker-1", ("wave",)))

  assert_that(result.changed, is_(True))
  assert_that(public.pack.stickers, equal_to({}))
  assert_that(
    caplog.messages,
    equal_to(["Removed sticker sticker-1 from tags wave"]),
  )


def test_delete_sticker_removes_from_private_pack_when_private_mode_is_enabled() -> None:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()
  public.ensure()
  user = StickfixUser(UserId(1))
  user.private_mode = True
  user.add_sticker("sticker-1", ["wave"])
  users.save_user(user)
  users.saved_users.clear()

  DeleteSticker(users, public)(DeleteStickerCommand(UserId(1), "sticker-1", ("wave",)))

  assert_that(user.stickers, equal_to({}))
