from typing import TYPE_CHECKING

from app.application.deal.history_writer import write_history
from app.domain.deal_action.history import next_action_status_draft

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.deal_action.inputs import NextActionStatusInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId


class ChangeNextActionStatus:
    """Next Action 상태를 바꾼다. 판정 순서는 없음(404) -> 담당자 아님(403) -> 422/409.

    바뀌면 Deal 이력에 한 건 남긴다. 실패하면 저장도 이력도 없다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, action_id: DealActionId, data: NextActionStatusInput, actor: Actor
    ) -> DealAction:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            action = await uow.deal_actions.get(action_id)
            action.ensure_status_changeable_by(actor.user_id, actor.role)
            change = action.change_next_action_status(data.status, data.memo, now)
            await uow.deal_actions.update(action)
            draft = next_action_status_draft(action.content, change)
            await write_history(uow, action.deal_code, actor.user_id, [draft], now)
            await uow.commit()
        return action
