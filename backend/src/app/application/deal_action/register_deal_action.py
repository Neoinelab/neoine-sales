from typing import TYPE_CHECKING

from app.domain.deal_action.entities import DealAction

if TYPE_CHECKING:
    from app.application.deal_action.inputs import DealActionInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.value_objects import DealId


class RegisterDealAction:
    """Deal에 활동을 기록한다. Deal이 없으면 DealNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, deal_id: DealId, data: DealActionInput) -> DealAction:
        details = data.to_details(deal_id)
        async with self._uow_factory() as uow:
            await uow.deals.get(deal_id)
            action = DealAction.create(details, self._clock.now())
            await uow.deal_actions.add(action)
            await uow.commit()
        return action
