"""DealHistoryRepository Port의 SQLAlchemy 구현. 이력은 불변이라 추가와 조회만 한다."""

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.domain.deal.code import DealCode
from app.domain.deal.history import DealHistoryEntry, HistoryCategory, HistoryDraft
from app.domain.user.value_objects import UserId
from app.infra.db.base_repository import SavepointWriter
from app.infra.db.models_deal import DealHistoryRow

if TYPE_CHECKING:
    from collections.abc import Sequence


def _to_row(entry: DealHistoryEntry) -> DealHistoryRow:
    return DealHistoryRow(
        deal_code=entry.deal_code.value,
        changed_at=entry.changed_at,
        changed_by_user_id=entry.changed_by,
        category=entry.draft.category.value,
        target=entry.draft.target,
        before_text=entry.draft.before,
        after_text=entry.draft.after,
    )


def _to_entity(row: DealHistoryRow) -> DealHistoryEntry:
    return DealHistoryEntry(
        id=row.id,
        deal_code=DealCode(row.deal_code),
        changed_at=row.changed_at,
        changed_by=UserId(row.changed_by_user_id),
        draft=HistoryDraft(
            HistoryCategory(row.category), row.target, row.before_text, row.after_text
        ),
    )


class SqlDealHistoryRepository(SavepointWriter):
    async def add_many(self, entries: Sequence[DealHistoryEntry]) -> None:
        """주어진 순서대로 저장한다(id는 DB가 순서대로 늘린다)."""
        rows = [_to_row(entry) for entry in entries]
        for row in rows:  # 한 행씩 flush해 INSERT 순서(= id 순서)를 입력 순서로 고정한다
            await self._insert(row, {})

    async def list(
        self, code: DealCode, *, category: HistoryCategory | None = None
    ) -> Sequence[DealHistoryEntry]:
        """변경 시각 내림차순, 같으면 id 내림차순(나중에 기록한 것이 위)."""
        statement = select(DealHistoryRow).where(DealHistoryRow.deal_code == code.value)
        if category is not None:
            statement = statement.where(DealHistoryRow.category == category.value)
        statement = statement.order_by(
            DealHistoryRow.changed_at.desc(), DealHistoryRow.id.desc()
        ).execution_options(populate_existing=True)
        return [_to_entity(row) for row in (await self._session.scalars(statement)).all()]
