"""DealActionRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from app.domain.common.errors import AlreadyExistsError
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.deal_action.value_objects import ActionType, DealActionDetails, DealActionId
from app.infra.db.base_repository import SqlRepository
from app.infra.db.like import LIKE_ESCAPE, like_pattern
from app.infra.db.models import DealActionRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Select

    from app.application.ports.deal_action_repository import DealActionQuery


def _apply_details(row: DealActionRow, details: DealActionDetails) -> None:
    row.deal_id = details.deal_id
    row.action_type = details.action_type.value
    row.title = details.title
    row.content = details.content
    row.acted_at = details.acted_at
    row.actor = details.actor


def _to_row(action: DealAction) -> DealActionRow:
    row = DealActionRow(
        id=action.id,
        created_at=action.created_at,
        updated_at=action.updated_at,
        deleted_at=action.deleted_at,
    )
    _apply_details(row, action.details)
    return row


def _to_entity(row: DealActionRow) -> DealAction:
    return DealAction(
        id=DealActionId(row.id),
        details=DealActionDetails(
            deal_id=DealId(row.deal_id),
            action_type=ActionType(row.action_type),
            title=row.title,
            content=row.content,
            acted_at=row.acted_at,
            actor=row.actor,
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _filtered(query: DealActionQuery) -> Select[DealActionRow]:
    statement = select(DealActionRow).where(DealActionRow.deleted_at.is_(None))
    if query.deal_id is not None:
        statement = statement.where(DealActionRow.deal_id == query.deal_id)
    if query.action_type is not None:
        statement = statement.where(DealActionRow.action_type == query.action_type.value)
    if query.actor is not None:
        statement = statement.where(DealActionRow.actor == query.actor)
    if query.acted_from is not None:
        statement = statement.where(DealActionRow.acted_at >= query.acted_from)
    if query.acted_to is not None:
        statement = statement.where(DealActionRow.acted_at < query.acted_to)
    if query.keyword is not None:
        pattern = like_pattern(query.keyword)
        statement = statement.where(
            or_(
                DealActionRow.title.ilike(pattern, escape=LIKE_ESCAPE),
                DealActionRow.content.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    return statement


class SqlDealActionRepository(SqlRepository[DealActionRow]):
    row_type = DealActionRow

    async def add(self, action: DealAction) -> None:
        await self._insert(
            _to_row(action), {"pk_deal_actions": lambda: AlreadyExistsError("Deal 활동", action.id)}
        )

    async def get(self, action_id: DealActionId, *, include_deleted: bool = False) -> DealAction:
        row = await self._find(action_id, include_deleted=include_deleted)
        if row is None:
            raise DealActionNotFoundError(action_id)
        return _to_entity(row)

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        statement = (
            _filtered(query)
            .order_by(DealActionRow.acted_at.desc(), DealActionRow.id)
            .offset(query.offset)
            .limit(query.limit)
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return [_to_entity(row) for row in rows]

    async def update(self, action: DealAction) -> None:
        row = await self._find(action.id, include_deleted=True)
        if row is None:
            raise DealActionNotFoundError(action.id)
        _apply_details(row, action.details)
        row.updated_at = action.updated_at
        row.deleted_at = action.deleted_at
        await self._save({})
