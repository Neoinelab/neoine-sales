"""DealRepository Port의 SQLAlchemy 구현. Deal Code 고유성은 DB UNIQUE 제약이 보장한다."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.exc import IntegrityError

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.common.errors import AlreadyExistsError
from app.domain.common.money import Money
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.entities import Deal
from app.domain.deal.errors import DealInUseError, DealNotFoundError, DuplicateDealCodeError
from app.domain.deal.pipeline import StageTotal
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import DealCode, DealDetails, DealId
from app.domain.partner.value_objects import PartnerId
from app.infra.db.base_repository import SqlRepository
from app.infra.db.like import keyword_filter
from app.infra.db.models import DealRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Select

    from app.application.ports.deal_repository import DealQuery


_IN_USE_CONSTRAINTS = ("fk_deal_actions_deal_id_deals", "fk_deal_stage_changes_deal_id_deals")


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
        stage=deal.stage.value,
        owner_user_id=deal.owner_user_id,
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
        stage=DealStage(row.stage),
        owner_user_id=row.owner_user_id,
    )


def _filtered(query: DealQuery) -> Select[DealRow]:
    statement = select(DealRow).where(DealRow.deleted_at.is_(None))
    if query.customer_id is not None:
        statement = statement.where(DealRow.customer_id == query.customer_id)
    if query.partner_id is not None:
        statement = statement.where(DealRow.partner_id == query.partner_id)
    if query.owner is not None:
        statement = statement.where(DealRow.owner == query.owner)
    if query.owner_user_id is not None:
        statement = statement.where(DealRow.owner_user_id == query.owner_user_id)
    if query.vendor is not None:
        statement = statement.where(DealRow.vendor == query.vendor)
    if query.revenue_from is not None:
        statement = statement.where(DealRow.revenue_date >= query.revenue_from)
    if query.revenue_to is not None:
        statement = statement.where(DealRow.revenue_date < query.revenue_to)
    if query.stage is not None:
        statement = statement.where(DealRow.stage == query.stage.value)
    if query.keyword is not None:
        statement = statement.where(
            keyword_filter(
                query.keyword,
                DealRow.code,
                DealRow.name,
                DealRow.owner,
                DealRow.vendor,
                DealRow.solution,
            )
        )
    return statement


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

    async def get(
        self, deal_id: DealId, *, include_deleted: bool = False, for_update: bool = False
    ) -> Deal:
        if for_update:
            locked = select(DealRow).where(DealRow.id == deal_id).with_for_update()
            row = (
                await self._session.scalars(locked.execution_options(populate_existing=True))
            ).one_or_none()
            if row is not None and row.deleted_at is not None and not include_deleted:
                row = None
        else:
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

    async def search(self, query: DealQuery) -> Sequence[Deal]:
        statement = (
            _filtered(query)
            .order_by(DealRow.created_at, DealRow.id)
            .offset(query.offset)
            .limit(query.limit)
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return [_to_entity(row) for row in rows]

    async def summarize_pipeline(self, *, owner_user_id: str | None = None) -> Sequence[StageTotal]:
        statement = (
            select(
                DealRow.stage,
                DealRow.revenue_currency,
                func.count().label("deal_count"),
                func.sum(DealRow.revenue_amount).label("amount"),
            )
            .where(DealRow.deleted_at.is_(None))
            .group_by(DealRow.stage, DealRow.revenue_currency)
        )
        if owner_user_id is not None:
            statement = statement.where(DealRow.owner_user_id == owner_user_id)
        rows = (await self._session.execute(statement)).all()
        return [
            StageTotal(DealStage(stage), currency, int(count), Decimal(amount))
            for stage, currency, count, amount in rows
        ]

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
        row.stage = deal.stage.value
        await self._save({"uq_deals_code": lambda: DuplicateDealCodeError(deal.details.code)})

    async def delete(self, deal_id: DealId) -> None:
        """물리 삭제. 활동·단계 이력이 FK(RESTRICT)로 막으면 DealInUseError."""
        row = await self._find(deal_id, include_deleted=True)
        if row is None:
            raise DealNotFoundError(deal_id)
        try:
            async with self._session.begin_nested():
                await self._session.delete(row)
                await self._session.flush()
        except IntegrityError as error:
            message = str(error.orig)
            if any(name in message for name in _IN_USE_CONSTRAINTS):
                raise DealInUseError(deal_id) from error
            raise
