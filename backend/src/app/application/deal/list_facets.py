from typing import TYPE_CHECKING

from app.application.deal.dto import DealFacets

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListDealFacets:
    """목록 필터에 쓸 Vendor·Solution 값."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> DealFacets:
        async with self._uow_factory() as uow:
            vendors, solutions = await uow.deals.facets()
        return DealFacets(vendors=vendors, solutions=solutions)
