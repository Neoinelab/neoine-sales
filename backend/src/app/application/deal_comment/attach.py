"""Action 등록·종료와 함께 남기는 Action Comment(CM-R14, CM-R15)."""

from typing import TYPE_CHECKING

from app.application.ids import new_deal_comment_id
from app.domain.deal_comment.entities import DealComment
from app.domain.deal_comment.history import comment_created_draft

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.deal.inputs import Actor
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.deal.history import HistoryDraft
    from app.domain.deal_action.entities import DealAction


async def attach_action_comment(
    uow: UnitOfWork, action: DealAction, text: str | None, actor: Actor, now: datetime
) -> list[HistoryDraft]:
    """text(`optional_comment`를 거친 값)가 있으면 action의 Action Comment를 저장한다.

    이력 초안을 돌려주고, 없으면 아무것도 하지 않고 빈 목록이다. action은 이미 저장된 행이다.
    """
    if text is None:
        return []
    deal = await uow.deals.get(action.deal_code)
    comment = DealComment.write(
        entity_id=await new_deal_comment_id(uow.ids),
        deal_code=action.deal_code,
        action_id=action.id,
        author_user_id=actor.user_id,
        body=text,
        now=now,
        deal_owner_id=deal.details.owner_user_id,
    )
    await uow.deal_comments.add(comment)
    return [comment_created_draft(text, action)]
