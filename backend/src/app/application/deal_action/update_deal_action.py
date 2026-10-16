from typing import TYPE_CHECKING

from app.application.deal.history_writer import write_history
from app.domain.deal_action.history import action_updated_draft

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.deal_action.inputs import ActionContentInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId


class UpdateDealAction:
    """Action의 내용을 고친다. 판정 순서는 없음(404) -> 담당자 아님(403) -> 입력 오류(422).

    내용이 그대로면 저장도 이력도 없다. 스냅숏·수행자·수행 일시·Deal은 바뀌지 않는다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, action_id: DealActionId, content: ActionContentInput, actor: Actor
    ) -> DealAction:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            action = await uow.deal_actions.get(action_id)
            action.ensure_editable_by(actor.user_id, actor.role)
            before = action.content
            after = content.to_content()
            if action.revise(after, now):
                await uow.deal_actions.update(action)
                draft = action_updated_draft(before, after)
                await write_history(uow, action.deal_code, actor.user_id, [draft], now)
                await uow.commit()
        return action
