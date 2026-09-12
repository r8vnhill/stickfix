from __future__ import annotations

import random

import pytest
from hamcrest import assert_that, equal_to, has_length, is_, none
from stickfix_domain import StickfixUser, UserId

from bot.application.errors import UserNotFoundError
from bot.application.requests import InlineQueryRequest
from bot.application.use_cases import ResolveInlineQuery
from tests.support.repositories import InMemoryPublicPackRepository, InMemoryUserRepository


class FakeHelpContentProvider:
  def __init__(self, help_text: str = "help text") -> None:
    self.help_text = help_text
    self.calls = 0

  def get_help_text(self) -> str:
    self.calls += 1
    return self.help_text


def make_use_case(
  users: InMemoryUserRepository,
  public: InMemoryPublicPackRepository,
  help_provider: FakeHelpContentProvider | None = None,
) -> ResolveInlineQuery:
  return ResolveInlineQuery(users, help_provider or FakeHelpContentProvider(), public)


def add_numbered_stickers(user: StickfixUser, tag: str, count: int) -> tuple[str, ...]:
  sticker_ids = tuple(f"sticker-{index:03d}" for index in range(count))
  for sticker_id in sticker_ids:
    user.add_sticker(sticker_id, [tag])
  return sticker_ids


def public_repository() -> tuple[InMemoryUserRepository, InMemoryPublicPackRepository]:
  users = InMemoryUserRepository()
  public = InMemoryPublicPackRepository()
  public_pack = public.ensure()
  public.save(public_pack)
  public.saved_packs.clear()
  return users, public


def test_missing_repository_user_falls_back_to_public_pack() -> None:
  users, public = public_repository()
  public.pack.add_sticker("public-sticker", ["wave"])

  result = make_use_case(users, public)(InlineQueryRequest(UserId(2), "wave"))

  assert_that(result.sticker_ids, equal_to(("public-sticker",)))
  assert_that(public.saved_packs, equal_to([public.pack]))


def test_none_user_id_falls_back_to_public_pack() -> None:
  users, public = public_repository()
  public.pack.add_sticker("public-sticker", ["wave"])

  result = make_use_case(users, public)(InlineQueryRequest(None, "wave"))

  assert_that(result.sticker_ids, equal_to(("public-sticker",)))
  assert_that(public.saved_packs, equal_to([public.pack]))


def test_missing_user_without_public_pack_raises_user_not_found() -> None:
  with pytest.raises(UserNotFoundError):
    make_use_case(InMemoryUserRepository(), InMemoryPublicPackRepository())(
      InlineQueryRequest(UserId(2), "wave")
    )


def test_public_mode_user_preserves_current_public_and_own_union_behaviour() -> None:
  users, public = public_repository()
  public.pack.add_sticker("public-sticker", ["wave"])
  user = StickfixUser(UserId(1))
  user.add_sticker("private-sticker", ["wave"])
  users.save_user(user)
  users.saved_users.clear()

  result = make_use_case(users, public)(InlineQueryRequest(UserId(1), "wave"))

  assert_that(set(result.sticker_ids), equal_to({"private-sticker", "public-sticker"}))
  assert_that(users.saved_users, equal_to([user]))


def test_private_mode_user_resolves_only_private_stickers() -> None:
  users, public = public_repository()
  public.pack.add_sticker("public-sticker", ["wave"])
  user = StickfixUser(UserId(1))
  user.private_mode = True
  user.add_sticker("private-sticker", ["wave"])
  users.save_user(user)
  users.saved_users.clear()

  result = make_use_case(users, public)(InlineQueryRequest(UserId(1), "wave"))

  assert_that(result.sticker_ids, equal_to(("private-sticker",)))
  assert_that(users.saved_users, equal_to([user]))


def test_empty_query_at_first_page_returns_help_metadata(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(random, "choice", lambda tags: "wave")
  users, public = public_repository()
  public.pack.add_sticker("empty-query-sticker", [""])
  public.pack.add_sticker("default-tag-sticker", ["wave"])
  help_provider = FakeHelpContentProvider("raw help")
  public.saved_packs.clear()

  result = make_use_case(users, public, help_provider)(InlineQueryRequest(None, ""))

  assert_that(result.show_default_help, is_(True))
  assert_that(result.help_text, equal_to("raw help"))
  assert_that(result.default_tags, equal_to(("wave",)))
  assert_that(result.sticker_ids, equal_to(("empty-query-sticker",)))
  assert_that(help_provider.calls, equal_to(1))


def test_empty_query_after_first_page_does_not_return_help_metadata() -> None:
  users, public = public_repository()
  public.pack.add_sticker("empty-query-sticker", [""])
  help_provider = FakeHelpContentProvider("raw help")
  public.saved_packs.clear()

  result = make_use_case(users, public, help_provider)(InlineQueryRequest(None, "", 49))

  assert_that(result.show_default_help, is_(False))
  assert_that(result.help_text, none())
  assert_that(result.default_tags, equal_to(()))
  assert_that(help_provider.calls, equal_to(0))


def test_non_empty_query_does_not_read_help_content() -> None:
  users, public = public_repository()
  public.pack.add_sticker("public-sticker", ["wave"])
  help_provider = FakeHelpContentProvider("raw help")
  public.saved_packs.clear()

  result = make_use_case(users, public, help_provider)(InlineQueryRequest(None, "wave"))

  assert_that(result.show_default_help, is_(False))
  assert_that(result.help_text, none())
  assert_that(help_provider.calls, equal_to(0))


def test_paginates_stickers_with_legacy_next_offset() -> None:
  users, public = public_repository()
  expected_stickers = add_numbered_stickers(public.pack, "wave", 100)
  public.saved_packs.clear()

  result = make_use_case(users, public)(InlineQueryRequest(None, "wave", 49))

  assert_that(result.sticker_ids, has_length(49))
  assert_that(set(result.sticker_ids).issubset(set(expected_stickers)), is_(True))
  assert_that(result.next_offset, equal_to(98))


def test_pagination_allows_fewer_than_limit_and_no_remaining_stickers() -> None:
  users, public = public_repository()
  add_numbered_stickers(public.pack, "wave", 2)
  public.saved_packs.clear()

  partial_result = make_use_case(users, public)(InlineQueryRequest(None, "wave", 1))
  empty_result = make_use_case(users, public)(InlineQueryRequest(None, "wave", 49))

  assert_that(partial_result.sticker_ids, has_length(1))
  assert_that(partial_result.next_offset, equal_to(50))
  assert_that(empty_result.sticker_ids, equal_to(()))
  assert_that(empty_result.next_offset, equal_to(98))


def test_private_lookup_saves_user_after_cache_mutation() -> None:
  users, public = public_repository()
  user = StickfixUser(UserId(1))
  user.private_mode = True
  user.add_sticker("private-sticker", ["wave"])
  users.save_user(user)
  users.saved_users.clear()

  make_use_case(users, public)(InlineQueryRequest(UserId(1), "wave"))

  assert_that(user.cache, equal_to({"wave": ["private-sticker"]}))
  assert_that(users.saved_users, equal_to([user]))
