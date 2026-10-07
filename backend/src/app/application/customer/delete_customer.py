from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.value_objects import CustomerId


class DeleteCustomer:
    """고객을 소프트 삭제한다. 이미 삭제됐거나 없으면 CustomerNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, customer_id: CustomerId) -> None:
        async with self._uow_factory() as uow:
            customer = await uow.customers.get(customer_id)
            customer.soft_delete(self._clock.now())
            await uow.customers.update(customer)
            await uow.commit()
