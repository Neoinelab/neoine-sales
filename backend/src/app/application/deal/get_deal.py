from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from app.domain.deal.value_objects import DealId


class GetDeal:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, deal_id: DealId) -> Deal:
        async with self._uow_factory() as uow:
            return await uow.deals.get(deal_id)
