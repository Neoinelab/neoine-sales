"""DealActionRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from sqlalchemy import exists, func, select

from app.domain.action_type.values import ActionTypeId, ActionTypeRef
from app.domain.code.values import CodeKind
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.sync_state import SyncState
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import DealActionNotFoundError
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from app.domain.deal_action.value_objects import ActionContent, DealActionId
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.deal_action_order import apply_order
from app.infra.db.deal_keys import deal_id_of
from app.infra.db.like import keyword_filter
from app.infra.db.models import DealActionRow
from app.infra.db.models_catalog import ActionTypeRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sqlalchemy import Select

    from app.application.ports.deal_action_repository import DealActionQuery


def _apply_content(row: DealActionRow, content: ActionContent) -> None:
    row.action_type_id = content.action_type.id
    row.action = content.action
    row.next_action = content.next_action
    row.due_date = content.due_date
    row.memo = content.memo


def _apply_state(row: DealActionRow, state: NextActionState | None) -> None:
    row.next_action_status = None if state is None else state.status.value
    row.next_action_closed_at = None if state is None else state.closed_at


def _state_of(row: DealActionRow) -> NextActionState | None:
    if row.next_action_status is None:
        return None
    return NextActionState(NextActionStatus(row.next_action_status), row.next_action_closed_at)


def _reference_errors(action: DealAction) -> ConstraintErrors:
    """FK 위반을 존재하지 않는 대상을 가리킨 것으로 바꾼다(삭제와의 경쟁 포함)."""
    snapshot = action.snapshot
    return {
        "fk_deal_actions_action_type_id_action_types": lambda: InvalidReferenceError(
            "Action 유형", action.content.action_type.id
        ),
        "fk_deal_actions_actor_user_id_users": lambda: InvalidReferenceError(
            "사용자", action.actor_user_id
        ),
        "fk_deal_actions_status_code": lambda: InvalidReferenceError(
            "Status 코드", snapshot.status_key
        ),
        "fk_deal_actions_forecast_code": lambda: InvalidReferenceError(
            "Forecast 코드", snapshot.forecast_key
        ),
    }


def _to_row(action: DealAction, deal_id: int) -> DealActionRow:
    row = DealActionRow(
        id=action.id,
        deal_id=deal_id,
        acted_at=action.acted_at,
        actor_user_id=action.actor_user_id,
        status_kind=CodeKind.STATUS.value,
        status_key=action.snapshot.status_key,
        forecast_kind=CodeKind.FORECAST.value,
        forecast_key=action.snapshot.forecast_key,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )
    _apply_content(row, action.content)
    _apply_state(row, action.next_action_state)
    return row


def _to_entity(row: DealActionRow, type_name: str, deal_code: str) -> DealAction:
    return DealAction(
        id=DealActionId(row.id),
        deal_code=DealCode(deal_code),
        content=ActionContent(
            action_type=ActionTypeRef(ActionTypeId(row.action_type_id), type_name),
            action=row.action,
            next_action=row.next_action,
            due_date=row.due_date,
            memo=row.memo,
        ),
        acted_at=row.acted_at,
        actor_user_id=UserId(row.actor_user_id),
        snapshot=SyncState(status_key=row.status_key, forecast_key=row.forecast_key),
        next_action_state=_state_of(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _with_type_name() -> Select[DealActionRow, str, str]:
    """행과 Action 유형 이름, 소속 Deal의 code(도메인은 deal_code로 Deal을 가리킨다)."""
    return (
        select(DealActionRow, ActionTypeRow.name, DealRow.deal_code)
        .join(ActionTypeRow, ActionTypeRow.id == DealActionRow.action_type_id)
        .join(DealRow, DealRow.id == DealActionRow.deal_id)
    )


def _filtered(query: DealActionQuery) -> Select[DealActionRow, str, str]:
    statement = _with_type_name().where(DealRow.deal_code == query.deal_code.value)
    if query.action_type_id is not None:
        statement = statement.where(DealActionRow.action_type_id == query.action_type_id)
    if query.actor_user_id is not None:
        statement = statement.where(DealActionRow.actor_user_id == query.actor_user_id)
    start, end = query.acted_window()
    if start is not None:
        statement = statement.where(DealActionRow.acted_at >= start)
    if end is not None:
        statement = statement.where(DealActionRow.acted_at < end)
    if query.due_from is not None:
        statement = statement.where(DealActionRow.due_date >= query.due_from)
    if query.due_to is not None:
        statement = statement.where(DealActionRow.due_date <= query.due_to)
    if query.next_action_status is not None:
        wanted = [status.value for status in query.next_action_status.statuses()]
        statement = statement.where(DealActionRow.next_action_status.in_(wanted))
    if query.keyword is not None:
        statement = statement.where(
            keyword_filter(
                query.keyword, DealActionRow.action, DealActionRow.next_action, DealActionRow.memo
            )
        )
    return statement


class SqlDealActionRepository(SqlRepository[DealActionRow]):
    row_type = DealActionRow

    async def add(self, action: DealAction) -> None:
        code = action.deal_code.value
        deal_id = await deal_id_of(self._session, code)
        if deal_id is None:
            raise DealNotFoundError(code)
        try:
            await self._insert(
                _to_row(action, deal_id),
                {
                    "pk_deal_actions": lambda: AlreadyExistsError("Deal 활동", action.id),
                    "fk_deal_actions_deal_id_deals": lambda: DealNotFoundError(code),
                    **_reference_errors(action),
                },
            )
        except InvalidReferenceError:
            # 여러 FK가 함께 어긋나면 DB가 먼저 보고하는 쪽이 정해져 있지 않다. Deal 없음 우선.
            if not await self._session.scalar(select(exists().where(DealRow.id == deal_id))):
                raise DealNotFoundError(code) from None
            raise

    async def get(self, action_id: DealActionId) -> DealAction:
        # 유형·Deal은 FK(RESTRICT·CASCADE)상 행이 있으면 항상 있으므로 inner join으로 읽는다.
        statement = _with_type_name().where(DealActionRow.id == action_id)
        found = (
            await self._session.execute(statement.execution_options(populate_existing=True))
        ).one_or_none()
        if found is None:
            raise DealActionNotFoundError(action_id)
        row, type_name, deal_code = found
        return _to_entity(row, type_name, deal_code)

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        statement = apply_order(_filtered(query), query.sort).execution_options(
            populate_existing=True
        )
        rows = (await self._session.execute(statement)).all()
        return [_to_entity(row, name, code) for row, name, code in rows]

    async def update(self, action: DealAction) -> None:
        """내용·Next Action 상태·updated_at만 쓴다. 수행 일시·수행자·스냅숏은 바뀌지 않는다."""
        row = await self._find(action.id)
        if row is None:
            raise DealActionNotFoundError(action.id)
        _apply_content(row, action.content)
        _apply_state(row, action.next_action_state)
        row.updated_at = action.updated_at
        await self._save({}, not_found=lambda: DealActionNotFoundError(action.id))

    async def delete(self, action_id: DealActionId) -> None:
        row = await self._find(action_id)
        if row is None:
            raise DealActionNotFoundError(action_id)
        await self._remove(row, {})

    async def count_by_action_type(self) -> Mapping[ActionTypeId, int]:
        column = DealActionRow.action_type_id
        statement = select(column, func.count()).group_by(column)
        return {
            ActionTypeId(type_id): int(count)
            for type_id, count in (await self._session.execute(statement)).all()
        }

    async def count_by_code(self, kind: CodeKind) -> Mapping[str, int]:
        column = DealActionRow.status_key if kind is CodeKind.STATUS else DealActionRow.forecast_key
        statement = select(column, func.count()).group_by(column)
        return {key: int(count) for key, count in (await self._session.execute(statement)).all()}
