from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.customer.entities import Customer
    from app.domain.customer.value_objects import CustomerId


class CustomerRepository(Protocol):
    """고객 저장소 계약. 삭제는 Customer.soft_delete 후 update로 저장한다."""

    async def add(self, customer: Customer) -> None:
        """새 고객을 저장한다. 같은 id가 있으면 AlreadyExistsError."""
        ...

    async def get(self, customer_id: CustomerId, *, include_deleted: bool = False) -> Customer:
        """없거나(삭제 제외 시) 삭제된 고객이면 CustomerNotFoundError."""
        ...

    async def list(
        self, *, offset: int = 0, limit: int = DEFAULT_LIMIT, include_deleted: bool = False
    ) -> Sequence[Customer]:
        """생성 시각 오름차순. 잘못된 offset/limit은 InvalidValueError."""
        ...

    async def update(self, customer: Customer) -> None:
        """변경 사항을 저장한다(삭제·복원 포함). 없으면 CustomerNotFoundError."""
        ...
