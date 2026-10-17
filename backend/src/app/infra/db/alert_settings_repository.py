"""AlertSettingsRepository Port의 SQLAlchemy 구현. 단일 행(id=1) upsert, 마지막 저장이 이긴다."""

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain.alert.settings import StoredAlertSettings
from app.domain.alert.thresholds import AlertThresholds
from app.domain.user.value_objects import UserId
from app.infra.db.models_alert import AlertSettingsRow

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_ROW_ID = 1


def _to_entity(row: AlertSettingsRow) -> StoredAlertSettings:
    return StoredAlertSettings(
        thresholds=AlertThresholds(row.stale_days),
        updated_at=row.updated_at,
        updated_by=UserId(row.updated_by_user_id),
    )


class SqlAlertSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> StoredAlertSettings | None:
        statement = (
            select(AlertSettingsRow)
            .where(AlertSettingsRow.id == _ROW_ID)
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        return _to_entity(row) if row else None

    async def save(
        self, thresholds: AlertThresholds, *, updated_by: UserId, now: datetime
    ) -> StoredAlertSettings:
        values = {
            "stale_days": thresholds.stale_days,
            "updated_at": now,
            "updated_by_user_id": updated_by,
        }
        statement = insert(AlertSettingsRow).values(id=_ROW_ID, **values)
        statement = statement.on_conflict_do_update(index_elements=["id"], set_=values)
        await self._session.execute(statement)
        stored = await self.get()
        if stored is None:  # 같은 트랜잭션에서 방금 쓴 행이므로 일어나지 않는다
            raise RuntimeError("alert settings row is missing after upsert")
        return stored
