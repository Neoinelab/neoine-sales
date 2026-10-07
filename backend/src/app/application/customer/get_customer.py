from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.customer.value_objects import CustomerId


class GetCustomer:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, customer_id: CustomerId) -> Customer:
        async with self._uow_factory() as uow:
            return await uow.customers.get(customer_id)
