"""StorageSettingsRepository Port의 SQLAlchemy 구현. 단일 행(id=1) upsert, 마지막 저장이 이긴다."""

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain.storage.path import StoragePath
from app.domain.storage.settings import StoredStorageSettings
from app.domain.user.value_objects import UserId
from app.infra.db.models_attachment import StorageSettingsRow

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_ROW_ID = 1


def _to_entity(row: StorageSettingsRow) -> StoredStorageSettings:
    return StoredStorageSettings(
        path=StoragePath(row.path),
        updated_at=row.updated_at,
        updated_by=UserId(row.updated_by_user_id) if row.updated_by_user_id else None,
    )


class SqlStorageSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> StoredStorageSettings | None:
        statement = (
            select(StorageSettingsRow)
            .where(StorageSettingsRow.id == _ROW_ID)
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        return _to_entity(row) if row else None

    async def save(
        self, path: StoragePath, *, updated_by: UserId | None, now: datetime
    ) -> StoredStorageSettings:
        values = {"path": path.value, "updated_at": now, "updated_by_user_id": updated_by}
        statement = insert(StorageSettingsRow).values(id=_ROW_ID, **values)
        statement = statement.on_conflict_do_update(index_elements=["id"], set_=values)
        await self._session.execute(statement)
        stored = await self.get()
        if stored is None:  # 같은 트랜잭션에서 방금 쓴 행이므로 일어나지 않는다
            raise RuntimeError("storage settings row is missing after upsert")
        return stored
