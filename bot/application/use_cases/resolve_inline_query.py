"""Use case for resolving inline query sticker results."""

from __future__ import annotations

from stickfix_domain import StickfixUser
from stickfix_domain.services import StickerPackService

from bot.application.ports import HelpContentProvider, PublicPackRepository, UserRepository
from bot.application.requests import InlineQueryRequest
from bot.application.results import InlineQueryResult

from ._base import StickerPackUseCase
from ._repositories import resolve_effective_user, save_effective_pack


class ResolveInlineQuery(StickerPackUseCase):
  """Turn an inline query into one page of sticker ids plus optional help.

  The empty query at ``offset == 0`` is special-cased: it returns a random
  default tag and the help text so the client can show a "how to use me"
  article; every other query just paginates the matched stickers. The effective
  pack is saved on each call because :class:`StickerPackService` may reshuffle
  or refresh its cache as a side effect of the lookup.
  """

  def __init__(
    self,
    users: UserRepository,
    help_content: HelpContentProvider,
    public: PublicPackRepository,
    stickers: StickerPackService | None = None,
  ) -> None:
    super().__init__(users, public, stickers)
    self._help_content = help_content

  def __call__(self, request: InlineQueryRequest) -> InlineQueryResult:
    public_pack = self._public.get()
    user = resolve_effective_user(self._users, request.user_id, public_pack)
    tags = tuple(request.query_text.split(" "))
    sticker_ids = self._stickers.find_stickers(user, tags, public_pack)
    paginated_stickers = sticker_ids[request.offset : request.offset + request.limit]
    default_tags, help_text = self._resolve_default_help(request, user, public_pack)

    save_effective_pack(self._users, self._public, user, public_pack)

    return InlineQueryResult(
      sticker_ids=paginated_stickers,
      default_tags=default_tags,
      show_default_help=help_text is not None,
      help_text=help_text,
      next_offset=request.offset + request.limit,
    )

  def _resolve_default_help(
    self,
    request: InlineQueryRequest,
    user: StickfixUser,
    public_pack: StickfixUser | None,
  ) -> tuple[tuple[str, ...], str | None]:
    if request.query_text != "" or request.offset != 0:
      return (), None

    default_tag_source = user if user.private_mode else public_pack
    default_tags = tuple(default_tag_source.random_tag()) if default_tag_source else ()
    return default_tags, self._help_content.get_help_text()
