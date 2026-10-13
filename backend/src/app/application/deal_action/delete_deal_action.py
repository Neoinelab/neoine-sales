from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.value_objects import DealActionId


class DeleteDealAction:
    """활동을 물리 삭제한다. 없으면 DealActionNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, action_id: DealActionId) -> None:
        async with self._uow_factory() as uow:
            await uow.deal_actions.get(action_id)
            await uow.deal_actions.delete(action_id)
            await uow.commit()
