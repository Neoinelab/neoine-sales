"""ActionTypeRepository Port의 SQLAlchemy 구현. 이름 고유성은 DB 유니크 인덱스가 보장한다."""

from typing import TYPE_CHECKING

from sqlalchemy import collate, func, select

from app.domain.action_type.entities import ActionType
from app.domain.action_type.errors import (
    ActionTypeInUseError,
    ActionTypeNotFoundError,
    DuplicateActionTypeNameError,
)
from app.domain.action_type.values import ActionTypeId
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.models import DealActionRow
from app.infra.db.models_catalog import ActionTypeRow

if TYPE_CHECKING:
    from collections.abc import Sequence


def _to_row(action_type: ActionType) -> ActionTypeRow:
    return ActionTypeRow(
        id=action_type.id,
        name=action_type.name,
        is_default=action_type.is_default,
        default_order=action_type.default_order,
        created_by_user_id=action_type.created_by_user_id,
        created_at=action_type.created_at,
        updated_at=action_type.updated_at,
    )


def _to_entity(row: ActionTypeRow) -> ActionType:
    return ActionType(
        id=ActionTypeId(row.id),
        name=row.name,
        is_default=row.is_default,
        default_order=row.default_order,
        created_by_user_id=UserId(row.created_by_user_id) if row.created_by_user_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _write_errors(action_type: ActionType) -> ConstraintErrors:
    return {
        "uq_action_types_name_lower": lambda: DuplicateActionTypeNameError(action_type.name),
        "pk_action_types": lambda: AlreadyExistsError("Action 유형", action_type.id),
        "fk_action_types_created_by_user_id_users": lambda: InvalidReferenceError(
            "사용자", action_type.created_by_user_id
        ),
    }


class SqlActionTypeRepository(SqlRepository[ActionTypeRow]):
    row_type = ActionTypeRow

    async def list(self, *, for_update: bool = False) -> Sequence[ActionType]:
        statement = select(ActionTypeRow).order_by(
            ActionTypeRow.is_default.desc(),
            ActionTypeRow.default_order,
            collate(func.lower(ActionTypeRow.name), "C"),  # 코드 포인트 순(Fake와 동일)
            ActionTypeRow.id,
        )
        if for_update:
            statement = statement.with_for_update()
        rows = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).all()
        return [_to_entity(row) for row in rows]

    async def get(self, type_id: ActionTypeId) -> ActionType:
        row = await self._find(type_id)
        if row is None:
            raise ActionTypeNotFoundError(type_id)
        return _to_entity(row)

    async def add(self, action_type: ActionType) -> None:
        await self._insert(_to_row(action_type), _write_errors(action_type))

    async def update(self, action_type: ActionType) -> None:
        row = await self._find(action_type.id)
        if row is None:
            raise ActionTypeNotFoundError(action_type.id)
        row.name = action_type.name
        row.updated_at = action_type.updated_at
        await self._save(
            _write_errors(action_type), not_found=lambda: ActionTypeNotFoundError(action_type.id)
        )

    async def delete(self, type_id: ActionTypeId) -> None:
        row = await self._find(type_id)
        if row is None:
            raise ActionTypeNotFoundError(type_id)
        in_use: ConstraintErrors = {
            "fk_deal_actions_action_type_id_action_types": lambda: ActionTypeInUseError(1)
        }
        try:
            await self._remove(row, in_use)
        except ActionTypeInUseError:
            raise ActionTypeInUseError(max(await self._usage(type_id), 1)) from None

    async def _usage(self, type_id: ActionTypeId) -> int:
        count = (
            select(func.count())
            .select_from(DealActionRow)
            .where(DealActionRow.action_type_id == type_id)
        )
        return int(await self._session.scalar(count) or 0)
