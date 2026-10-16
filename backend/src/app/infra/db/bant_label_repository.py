"""BantLabelRepository Port의 SQLAlchemy 구현. 이름 고유성은 DB 유니크 인덱스가 보장한다."""

from typing import TYPE_CHECKING

from sqlalchemy import case, collate, func, select

from app.domain.bant.entities import BantLabel
from app.domain.bant.errors import BantLabelNotFoundError, DuplicateLabelNameError, LabelInUseError
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.models_catalog import BantLabelRow
from app.infra.db.models_deal import DealBantLabelRow

if TYPE_CHECKING:
    from collections.abc import Sequence

_CATEGORY_ORDER = case(
    {category.value: index for index, category in enumerate(BantCategory)},
    value=BantLabelRow.category,
)


def _to_row(label: BantLabel) -> BantLabelRow:
    return BantLabelRow(
        id=label.id,
        category=label.category.value,
        name=label.name,
        is_default=label.is_default,
        default_order=label.default_order,
        created_by_user_id=label.created_by_user_id,
        created_at=label.created_at,
        updated_at=label.updated_at,
    )


def _to_entity(row: BantLabelRow) -> BantLabel:
    return BantLabel(
        id=BantLabelId(row.id),
        category=BantCategory(row.category),
        name=row.name,
        is_default=row.is_default,
        default_order=row.default_order,
        created_by_user_id=UserId(row.created_by_user_id) if row.created_by_user_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _write_errors(label: BantLabel) -> ConstraintErrors:
    return {
        "uq_bant_labels_category_name_lower": lambda: DuplicateLabelNameError(label.name),
        "pk_bant_labels": lambda: AlreadyExistsError("Label", label.id),
        "fk_bant_labels_created_by_user_id_users": lambda: InvalidReferenceError(
            "사용자", label.created_by_user_id
        ),
    }


class SqlBantLabelRepository(SqlRepository[BantLabelRow]):
    row_type = BantLabelRow

    async def list(
        self, category: BantCategory | None = None, *, for_update: bool = False
    ) -> Sequence[BantLabel]:
        statement = select(BantLabelRow).order_by(
            _CATEGORY_ORDER,
            BantLabelRow.is_default.desc(),
            BantLabelRow.default_order,
            collate(
                func.lower(BantLabelRow.name), "C"
            ),  # 코드 포인트 순(Fake의 파이썬 비교와 동일)
            BantLabelRow.id,
        )
        if category is not None:
            statement = statement.where(BantLabelRow.category == category.value)
        if for_update:
            statement = statement.with_for_update()
        rows = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).all()
        return [_to_entity(row) for row in rows]

    async def get(self, label_id: BantLabelId) -> BantLabel:
        row = await self._find(label_id)
        if row is None:
            raise BantLabelNotFoundError(label_id)
        return _to_entity(row)

    async def add(self, label: BantLabel) -> None:
        await self._insert(_to_row(label), _write_errors(label))

    async def update(self, label: BantLabel) -> None:
        row = await self._find(label.id)
        if row is None:
            raise BantLabelNotFoundError(label.id)
        row.name = label.name
        row.updated_at = label.updated_at
        await self._save(_write_errors(label), not_found=lambda: BantLabelNotFoundError(label.id))

    async def delete(self, label_id: BantLabelId) -> None:
        row = await self._find(label_id)
        if row is None:
            raise BantLabelNotFoundError(label_id)
        in_use: ConstraintErrors = {"fk_deal_bant_labels_label": lambda: LabelInUseError(1)}
        try:
            await self._remove(row, in_use)
        except LabelInUseError:
            raise LabelInUseError(max(await self._linked_deals(label_id), 1)) from None

    async def _linked_deals(self, label_id: BantLabelId) -> int:
        count = (
            select(func.count())
            .select_from(DealBantLabelRow)
            .where(DealBantLabelRow.label_id == label_id)
        )
        return int(await self._session.scalar(count) or 0)
