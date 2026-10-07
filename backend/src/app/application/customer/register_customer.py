from typing import TYPE_CHECKING

from app.domain.customer.entities import Customer

if TYPE_CHECKING:
    from app.application.customer.inputs import CustomerInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class RegisterCustomer:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, data: CustomerInput) -> Customer:
        details = data.to_details()  # 입력 검증은 트랜잭션을 열기 전에 끝낸다
        async with self._uow_factory() as uow:
            customer = Customer.create(details, self._clock.now())
            await uow.customers.add(customer)
            await uow.commit()
        return customer
