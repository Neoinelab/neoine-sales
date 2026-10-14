"""DealActionRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from sqlalchemy import exists, select

from app.application.ports.deal_action_repository import DealActionSort
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.deal_action.value_objects import ActionType, DealActionDetails, DealActionId
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.like import keyword_filter
from app.infra.db.models import DealActionRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Select

    from app.application.ports.deal_action_repository import DealActionQuery


def _apply_details(row: DealActionRow, details: DealActionDetails) -> None:
    row.deal_id = details.deal_id
    row.action_type = details.action_type.value
    row.action = details.action
    row.next_action = details.next_action
    row.due_date = details.due_date
    row.memo = details.memo
    row.acted_at = details.acted_at
    row.actor_user_id = details.actor_user_id


def _user_errors(action: DealAction) -> ConstraintErrors:
    """활동자 FK 위반(삭제와의 경쟁)은 존재하지 않는 사용자를 지정한 것과 같다."""
    return {
        "fk_deal_actions_actor_user_id_users": lambda: InvalidReferenceError(
            "사용자", action.details.actor_user_id
        )
    }


def _to_row(action: DealAction) -> DealActionRow:
    row = DealActionRow(
        id=action.id,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )
    _apply_details(row, action.details)
    return row


def _to_entity(row: DealActionRow) -> DealAction:
    return DealAction(
        id=DealActionId(row.id),
        details=DealActionDetails(
            deal_id=DealId(row.deal_id),
            action_type=ActionType(row.action_type),
            action=row.action,
            next_action=row.next_action,
            due_date=row.due_date,
            memo=row.memo,
            acted_at=row.acted_at,
            actor_user_id=UserId(row.actor_user_id),
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _filtered(query: DealActionQuery) -> Select[DealActionRow]:
    statement = select(DealActionRow)
    if query.deal_id is not None:
        statement = statement.where(DealActionRow.deal_id == query.deal_id)
    if query.action_type is not None:
        statement = statement.where(DealActionRow.action_type == query.action_type.value)
    if query.actor_user_id is not None:
        statement = statement.where(DealActionRow.actor_user_id == query.actor_user_id)
    if query.acted_from is not None:
        statement = statement.where(DealActionRow.acted_at >= query.acted_from)
    if query.acted_to is not None:
        statement = statement.where(DealActionRow.acted_at < query.acted_to)
    if query.due_from is not None:
        statement = statement.where(DealActionRow.due_date >= query.due_from)
    if query.due_to is not None:
        statement = statement.where(DealActionRow.due_date <= query.due_to)
    if query.keyword is not None:
        statement = statement.where(
            keyword_filter(
                query.keyword, DealActionRow.action, DealActionRow.next_action, DealActionRow.memo
            )
        )
    return statement


def _ordered(statement: Select[DealActionRow], sort: DealActionSort) -> Select[DealActionRow]:
    """정렬. 계획 일정 정렬은 NULL을 항상 뒤로 보내고, 동률은 acted_at 최신순 -> id."""
    tie_breakers = (DealActionRow.acted_at.desc(), DealActionRow.id)
    if sort is DealActionSort.DUE_DATE_ASC:
        return statement.order_by(DealActionRow.due_date.asc().nulls_last(), *tie_breakers)
    if sort is DealActionSort.DUE_DATE_DESC:
        return statement.order_by(DealActionRow.due_date.desc().nulls_last(), *tie_breakers)
    return statement.order_by(*tie_breakers)


class SqlDealActionRepository(SqlRepository[DealActionRow]):
    row_type = DealActionRow

    async def add(self, action: DealAction) -> None:
        await self._insert(
            _to_row(action),
            {
                "pk_deal_actions": lambda: AlreadyExistsError("Deal 활동", action.id),
                "fk_deal_actions_deal_id_deals": lambda: DealNotFoundError(action.details.deal_id),
                **_user_errors(action),
            },
        )

    async def get(self, action_id: DealActionId) -> DealAction:
        row = await self._find(action_id)
        if row is None:
            raise DealActionNotFoundError(action_id)
        return _to_entity(row)

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        statement = (
            _ordered(_filtered(query), query.sort)
            .offset(query.offset)
            .limit(query.limit)
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return [_to_entity(row) for row in rows]

    async def update(self, action: DealAction) -> None:
        row = await self._find(action.id)
        if row is None:
            raise DealActionNotFoundError(action.id)
        _apply_details(row, action.details)
        row.updated_at = action.updated_at
        await self._save(_user_errors(action), not_found=lambda: DealActionNotFoundError(action.id))

    async def delete(self, action_id: DealActionId) -> None:
        row = await self._find(action_id)
        if row is None:
            raise DealActionNotFoundError(action_id)
        await self._remove(row, {})

    async def exists_for_deal(self, deal_id: DealId) -> bool:
        """이 Deal의 활동 행이 하나라도 있으면 True."""
        statement = select(exists().where(DealActionRow.deal_id == deal_id))
        return bool(await self._session.scalar(statement))
