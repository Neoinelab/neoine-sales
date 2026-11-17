from typing import TYPE_CHECKING

from app.application.deal_comment.build_views import to_views
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.deal_comment.views import DealCommentView
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.value_objects import DealActionId


class ListDealComments:
    """Deal 소속 Comment를 최근순으로 돌려준다. action_id를 주면 그 Action의 것만(없으면 0건)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, code: str, action_id: DealActionId | None = None
    ) -> Sequence[DealCommentView]:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        async with self._uow_factory() as uow:
            await uow.deals.get(deal_code)
            comments = await uow.deal_comments.list_for_deal(deal_code, action_id=action_id)
            return await to_views(uow, comments)
