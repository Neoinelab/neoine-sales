from typing import TYPE_CHECKING

from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_comment.errors import DealCommentReadForbiddenError
from app.domain.deal_comment.policy import can_mark_comments_read

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_comment.values import DealCommentId


class MarkDealCommentsRead:
    """Deal의 Comment를 읽음 처리한다. 판정 순서는 없는 Deal(404) -> Owner 아님(403) -> 처리.

    그 Deal 소속이 아니거나 없거나 이미 읽은 id는 건너뛰고(read_at 불변), 이력은 남기지 않는다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, code: str, actor: Actor, comment_ids: Sequence[DealCommentId]) -> None:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_code)
            if not can_mark_comments_read(actor.user_id, deal.details.owner_user_id):
                raise DealCommentReadForbiddenError
            await uow.deal_comments.mark_read(deal_code, list(dict.fromkeys(comment_ids)), now)
            await uow.commit()
