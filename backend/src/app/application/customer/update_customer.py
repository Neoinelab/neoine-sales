from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.customer.inputs import CustomerInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer
    from app.domain.customer.value_objects import CustomerId


class UpdateCustomer:
    """고객 정보를 전체 교체한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, customer_id: CustomerId, data: CustomerInput) -> Customer:
        details = data.to_details()
        async with self._uow_factory() as uow:
            customer = await uow.customers.get(customer_id)
            customer.update(details, self._clock.now())
            await uow.customers.update(customer)
            await uow.commit()
        return customer
