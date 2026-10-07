"""DealRepository Port의 SQLAlchemy 구현. Deal Code 고유성은 DB UNIQUE 제약이 보장한다."""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, exists, select

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.common.errors import AlreadyExistsError
from app.domain.common.money import Money
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.entities import Deal
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.domain.deal.value_objects import DealCode, DealDetails, DealId
from app.domain.partner.value_objects import PartnerId
from app.infra.db.base_repository import SqlRepository
from app.infra.db.models import DealRow

if TYPE_CHECKING:
    from collections.abc import Sequence


def _apply_details(row: DealRow, details: DealDetails) -> None:
    row.code = details.code.value
    row.name = details.name
    row.owner = details.owner
    row.vendor = details.vendor
    row.solution = details.solution
    row.revenue_amount = details.revenue.amount
    row.revenue_currency = details.revenue.currency
    row.revenue_date = details.revenue_date
    row.customer_id = details.customer_id
    row.partner_id = details.partner_id


def _to_row(deal: Deal) -> DealRow:
    row = DealRow(
        id=deal.id,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        deleted_at=deal.deleted_at,
    )
    _apply_details(row, deal.details)
    return row


def _to_entity(row: DealRow) -> Deal:
    return Deal(
        id=DealId(row.id),
        details=DealDetails(
            code=DealCode(row.code),
            name=row.name,
            owner=row.owner,
            vendor=row.vendor,
            solution=row.solution,
            revenue=Money(row.revenue_amount, row.revenue_currency),
            revenue_date=row.revenue_date,
            customer_id=CustomerId(row.customer_id),
            partner_id=PartnerId(row.partner_id) if row.partner_id else None,
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlDealRepository(SqlRepository[DealRow]):
    row_type = DealRow

    async def add(self, deal: Deal) -> None:
        await self._insert(
            _to_row(deal),
            {
                "pk_deals": lambda: AlreadyExistsError("Deal", deal.id),
                "uq_deals_code": lambda: DuplicateDealCodeError(deal.details.code),
            },
        )

    async def get(self, deal_id: DealId, *, include_deleted: bool = False) -> Deal:
        row = await self._find(deal_id, include_deleted=include_deleted)
        if row is None:
            raise DealNotFoundError(deal_id)
        return _to_entity(row)

    async def get_by_code(self, code: DealCode, *, include_deleted: bool = False) -> Deal:
        statement = (
            select(DealRow)
            .where(DealRow.code == code.value)
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        if row is None or (row.deleted_at is not None and not include_deleted):
            raise DealNotFoundError(code)
        return _to_entity(row)

    async def list(
        self, *, offset: int = 0, limit: int = DEFAULT_LIMIT, include_deleted: bool = False
    ) -> Sequence[Deal]:
        rows = await self._page(offset, limit, include_deleted=include_deleted)
        return [_to_entity(row) for row in rows]

    async def has_active_for_customer(self, customer_id: CustomerId) -> bool:
        return await self._has_active(DealRow.customer_id == customer_id)

    async def has_active_for_partner(self, partner_id: PartnerId) -> bool:
        return await self._has_active(DealRow.partner_id == partner_id)

    async def _has_active(self, condition: ColumnElement[bool]) -> bool:
        statement = select(exists().where(condition, DealRow.deleted_at.is_(None)))
        return bool(await self._session.scalar(statement))

    async def update(self, deal: Deal) -> None:
        row = await self._find(deal.id, include_deleted=True)
        if row is None:
            raise DealNotFoundError(deal.id)
        _apply_details(row, deal.details)
        row.updated_at = deal.updated_at
        row.deleted_at = deal.deleted_at
        await self._save({"uq_deals_code": lambda: DuplicateDealCodeError(deal.details.code)})
