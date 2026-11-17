from typing import TYPE_CHECKING

from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from app.application.deal_comment.views import UnreadCommentCounts
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class CountUnreadDealComments:
    """Deal의 읽지 않은 Comment 수(전체와 Action별). 없는 Deal은 404."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, code: str) -> UnreadCommentCounts:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        async with self._uow_factory() as uow:
            await uow.deals.get(deal_code)
            return await uow.deal_comments.unread_counts(deal_code)
