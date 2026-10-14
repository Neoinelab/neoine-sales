from typing import TYPE_CHECKING

from app.application.user.assignment import ensure_assignable

if TYPE_CHECKING:
    from app.application.deal_action.inputs import DealActionInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId


class UpdateDealAction:
    """활동을 전체 교체한다. 소속 Deal은 바뀌지 않는다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, action_id: DealActionId, data: DealActionInput) -> DealAction:
        async with self._uow_factory() as uow:
            action = await uow.deal_actions.get(action_id)
            details = data.to_details(action.details.deal_id)
            await ensure_assignable(
                uow, details.actor_user_id, unchanged_from=action.details.actor_user_id
            )
            action.update(details, self._clock.now())
            await uow.deal_actions.update(action)
            await uow.commit()
        return action
