from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal_action.value_objects import DealActionId


class DeleteDealAction:
    """활동을 소프트 삭제한다. 없거나 이미 삭제됐으면 DealActionNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, action_id: DealActionId) -> None:
        async with self._uow_factory() as uow:
            action = await uow.deal_actions.get(action_id)
            action.soft_delete(self._clock.now())
            await uow.deal_actions.update(action)
            await uow.commit()
