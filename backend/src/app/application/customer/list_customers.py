from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.customer_repository import CustomerQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer


class ListCustomers:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: CustomerQuery) -> Sequence[Customer]:
        async with self._uow_factory() as uow:
            return await uow.customers.search(query)
