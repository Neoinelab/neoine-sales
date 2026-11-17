from typing import TYPE_CHECKING

from app.application.deal.history_writer import write_history
from app.application.deal_comment.linked_action import linked_action
from app.application.ids import new_deal_comment_id
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_comment.entities import DealComment
from app.domain.deal_comment.history import comment_created_draft
from app.domain.deal_comment.values import comment_body

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.deal_comment.inputs import DealCommentInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class WriteDealComment:
    """Deal(또는 그 Deal의 Action)에 Comment를 쓴다. 작성자·시각은 서버가 정한다.

    판정 순서는 없는 Deal(404) -> 본문(422) -> 연결 Action(422)이다. Comment와 이력은 한
    트랜잭션이고 Deal·Action 값은 바꾸지 않는다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, code: str, data: DealCommentInput, actor: Actor) -> DealComment:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_code)
            body = comment_body(data.body)
            action = await linked_action(uow, deal_code, data.action_id)
            comment = DealComment.write(
                entity_id=await new_deal_comment_id(uow.ids),
                deal_code=deal_code,
                action_id=data.action_id,
                author_user_id=actor.user_id,
                body=body,
                now=now,
                deal_owner_id=deal.details.owner_user_id,
            )
            await uow.deal_comments.add(comment)
            draft = comment_created_draft(body, action)
            await write_history(uow, deal_code, actor.user_id, [draft], now)
            await uow.commit()
        return comment
