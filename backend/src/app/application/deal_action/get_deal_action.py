from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId


class GetDealAction:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, action_id: DealActionId) -> DealAction:
        async with self._uow_factory() as uow:
            return await uow.deal_actions.get(action_id)
