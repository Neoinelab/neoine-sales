from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.value_objects import DealId


class DeleteDeal:
    """Deal을 소프트 삭제한다. 삭제된 Deal의 코드는 다시 쓸 수 없다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, deal_id: DealId) -> None:
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_id)
            deal.soft_delete(self._clock.now())
            await uow.deals.update(deal)
            await uow.commit()
