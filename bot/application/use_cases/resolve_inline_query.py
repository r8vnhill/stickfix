"""Use case for resolving inline query sticker results."""

from __future__ import annotations

from bot.application.ports import HelpContentProvider, PublicPackRepository, UserRepository
from bot.application.requests import InlineQueryRequest
from bot.application.results import InlineQueryResult
from bot.domain.services import StickerPackService
from bot.domain.user import StickfixUser

from ._repositories import public_repository, resolve_effective_user, save_effective_pack


class ResolveInlineQuery:
    """Resolve stickers and default-help metadata for Telegram inline queries."""

    def __init__(
        self,
        users: UserRepository,
        help_content: HelpContentProvider,
        public: PublicPackRepository | None = None,
        stickers: StickerPackService | None = None,
    ) -> None:
        self._users = users
        self._public = public_repository(users, public)
        self._help_content = help_content
        self._stickers = stickers or StickerPackService()

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
