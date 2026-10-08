from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.deal_repository import DealQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal


class ListDeals:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: DealQuery) -> Sequence[Deal]:
        async with self._uow_factory() as uow:
            return await uow.deals.search(query)
