"""CustomerRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import AlreadyExistsError
from app.domain.customer.entities import Customer
from app.domain.customer.errors import CustomerNotFoundError
from app.domain.customer.value_objects import CustomerDetails, CustomerId
from app.infra.db.base_repository import SqlRepository
from app.infra.db.like import keyword_filter
from app.infra.db.models import CustomerRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.customer_repository import CustomerQuery


def _apply_details(row: CustomerRow, details: CustomerDetails) -> None:
    row.company_name = details.company_name
    row.contact_name = details.contact_name
    row.contact_title = details.contact_title
    row.email = details.email.value if details.email else None
    row.phone = details.phone.value if details.phone else None
    row.employee_count = details.employee_count
    row.notes = details.notes


def _to_row(customer: Customer) -> CustomerRow:
    row = CustomerRow(
        id=customer.id,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        deleted_at=customer.deleted_at,
    )
    _apply_details(row, customer.details)
    return row


def _to_entity(row: CustomerRow) -> Customer:
    return Customer(
        id=CustomerId(row.id),
        details=CustomerDetails(
            company_name=row.company_name,
            contact_name=row.contact_name,
            contact_title=row.contact_title,
            email=Email(row.email) if row.email else None,
            phone=PhoneNumber(row.phone) if row.phone else None,
            employee_count=row.employee_count,
            notes=row.notes,
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlCustomerRepository(SqlRepository[CustomerRow]):
    row_type = CustomerRow

    async def add(self, customer: Customer) -> None:
        await self._insert(
            _to_row(customer), {"pk_customers": lambda: AlreadyExistsError("고객", customer.id)}
        )

    async def get(self, customer_id: CustomerId, *, include_deleted: bool = False) -> Customer:
        row = await self._find(customer_id, include_deleted=include_deleted)
        if row is None:
            raise CustomerNotFoundError(customer_id)
        return _to_entity(row)

    async def list(
        self, *, offset: int = 0, limit: int = DEFAULT_LIMIT, include_deleted: bool = False
    ) -> Sequence[Customer]:
        rows = await self._page(offset, limit, include_deleted=include_deleted)
        return [_to_entity(row) for row in rows]

    async def search(self, query: CustomerQuery) -> Sequence[Customer]:
        condition = (
            None
            if query.keyword is None
            else keyword_filter(
                query.keyword,
                CustomerRow.company_name,
                CustomerRow.contact_name,
                CustomerRow.contact_title,
                CustomerRow.email,
                CustomerRow.phone,
            )
        )
        rows = await self._page(
            query.offset, query.limit, include_deleted=False, condition=condition
        )
        return [_to_entity(row) for row in rows]

    async def update(self, customer: Customer) -> None:
        row = await self._find(customer.id, include_deleted=True)
        if row is None:
            raise CustomerNotFoundError(customer.id)
        _apply_details(row, customer.details)
        row.updated_at = customer.updated_at
        row.deleted_at = customer.deleted_at
        await self._save({})
