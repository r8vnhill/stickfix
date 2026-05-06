"""Use case for resolving inline query sticker results."""

from __future__ import annotations

from bot.application.errors import UserNotFoundError
from bot.application.ports import HelpContentProvider, UserRepository
from bot.application.requests import InlineQueryRequest
from bot.application.results import InlineQueryResult
from bot.domain.services import StickerPackService
from bot.domain.user import StickfixUser


class ResolveInlineQuery:
    """Resolve stickers and default-help metadata for Telegram inline queries."""

    def __init__(
        self,
        users: UserRepository,
        help_content: HelpContentProvider,
        stickers: StickerPackService | None = None,
    ) -> None:
        self._users = users
        self._help_content = help_content
        self._stickers = stickers or StickerPackService()

    def __call__(self, request: InlineQueryRequest) -> InlineQueryResult:
        public_pack = self._users.get_public_pack()
        user = self._resolve_request_user(request.user_id, public_pack)
        tags = tuple(request.query_text.split(" "))
        sticker_ids = self._stickers.find_stickers(user, tags, public_pack)
        paginated_stickers = sticker_ids[request.offset : request.offset + request.limit]
        default_tags, help_text = self._resolve_default_help(request, user, public_pack)

        self._users.save_user(user)

        return InlineQueryResult(
            sticker_ids=paginated_stickers,
            default_tags=default_tags,
            show_default_help=help_text is not None,
            help_text=help_text,
            next_offset=request.offset + request.limit,
        )

    def _resolve_request_user(
        self,
        user_id: str | None,
        public_pack: StickfixUser | None,
    ) -> StickfixUser:
        user = self._users.get_user(user_id) if user_id is not None else None
        if user is not None:
            return user
        if public_pack is None:
            raise UserNotFoundError("No user or public sticker pack exists.")
        return public_pack

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
