from typing import TYPE_CHECKING

from app.application.deal.history_writer import write_history
from app.domain.deal_action.history import action_deleted_draft

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.value_objects import DealActionId


class DeleteDealAction:
    """Action을 물리 삭제하고 이력을 남긴다. 없으면 404, 담당자(본인·admin)가 아니면 403."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, action_id: DealActionId, actor: Actor) -> None:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            action = await uow.deal_actions.get(action_id)
            action.ensure_deletable_by(actor.user_id, actor.role)
            await uow.deal_actions.delete(action_id)
            draft = action_deleted_draft(action.content)
            await write_history(uow, action.deal_code, actor.user_id, [draft], now)
            await uow.commit()
