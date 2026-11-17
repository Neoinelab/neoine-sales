from typing import TYPE_CHECKING

from app.application.deal.history_writer import write_history
from app.application.deal_comment.linked_action import linked_action
from app.domain.deal_comment.history import comment_deleted_draft

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_comment.values import DealCommentId


class DeleteDealComment:
    """Comment를 물리 삭제하고 이력을 남긴다. 없으면 404, 작성자(본인 sales)·admin이 아니면 403."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, comment_id: DealCommentId, actor: Actor) -> None:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            comment = await uow.deal_comments.get(comment_id, for_update=True)
            comment.ensure_deletable_by(actor.user_id, actor.role)
            action = await linked_action(uow, comment.deal_code, comment.action_id)
            await uow.deal_comments.delete(comment_id)
            draft = comment_deleted_draft(comment.body, action)
            await write_history(uow, comment.deal_code, actor.user_id, [draft], now)
            await uow.commit()
