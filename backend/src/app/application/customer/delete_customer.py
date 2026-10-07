from typing import TYPE_CHECKING

from app.domain.customer.errors import CustomerInUseError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.value_objects import CustomerId


class DeleteCustomer:
    """고객을 소프트 삭제한다. 없으면 NotFound, 활성 Deal이 있으면 CustomerInUseError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, customer_id: CustomerId) -> None:
        async with self._uow_factory() as uow:
            customer = await uow.customers.get(customer_id)
            if await uow.deals.has_active_for_customer(customer_id):
                raise CustomerInUseError(customer_id)
            customer.soft_delete(self._clock.now())
            await uow.customers.update(customer)
            await uow.commit()
