"""DealStageChangeRepository Port의 SQLAlchemy 구현. 이력은 불변이라 추가와 조회만 있다."""

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.common.errors import AlreadyExistsError
from app.domain.deal.stage import DealStage, DealStageChange, DealStageChangeId, StageChanger
from app.domain.deal.value_objects import DealId
from app.infra.db.models import DealStageChangeRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.ports.deal_stage_change_repository import DealStageChangeQuery


def _to_row(change: DealStageChange) -> DealStageChangeRow:
    return DealStageChangeRow(
        id=change.id,
        deal_id=change.deal_id,
        from_stage=change.from_stage.value,
        to_stage=change.to_stage.value,
        reason=change.reason,
        changed_by_subject=change.changed_by.subject,
        changed_by_name=change.changed_by.name,
        changed_at=change.changed_at,
    )


def _to_entity(row: DealStageChangeRow) -> DealStageChange:
    return DealStageChange(
        id=DealStageChangeId(row.id),
        deal_id=DealId(row.deal_id),
        from_stage=DealStage(row.from_stage),
        to_stage=DealStage(row.to_stage),
        reason=row.reason,
        changed_by=StageChanger(subject=row.changed_by_subject, name=row.changed_by_name),
        changed_at=row.changed_at,
    )


class SqlDealStageChangeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, change: DealStageChange) -> None:
        """SAVEPOINT 안에서 flush해, 중복 id가 나도 바깥 트랜잭션이 오염되지 않게 한다."""
        try:
            async with self._session.begin_nested():
                self._session.add(_to_row(change))
                await self._session.flush()
        except IntegrityError as error:
            if "pk_deal_stage_changes" in str(error.orig):
                raise AlreadyExistsError("단계 이력", change.id) from error
            raise

    async def search(self, query: DealStageChangeQuery) -> Sequence[DealStageChange]:
        statement = (
            select(DealStageChangeRow)
            .where(DealStageChangeRow.deal_id == query.deal_id)
            .order_by(DealStageChangeRow.changed_at.desc(), DealStageChangeRow.id)
            .offset(query.offset)
            .limit(query.limit)
            .execution_options(populate_existing=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return [_to_entity(row) for row in rows]
