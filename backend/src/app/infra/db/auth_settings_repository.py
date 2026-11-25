"""AuthSettingsRepository Port의 SQLAlchemy 구현. 단일 행(id=1) upsert."""

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain.auth.mode import AuthMode, AuthSettings
from app.infra.db.models_auth import AuthSettingsRow

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_ROW_ID = 1


class SqlAuthSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> AuthSettings | None:
        statement = (
            select(AuthSettingsRow)
            .where(AuthSettingsRow.id == _ROW_ID)
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        return AuthSettings(AuthMode(row.mode), row.updated_at, row.setup_pending) if row else None

    async def save(
        self, mode: AuthMode, *, now: datetime, setup_pending: bool = False
    ) -> AuthSettings:
        values = {"mode": mode.value, "updated_at": now, "setup_pending": setup_pending}
        statement = (
            insert(AuthSettingsRow)
            .values(id=_ROW_ID, **values)
            .on_conflict_do_update(index_elements=[AuthSettingsRow.id], set_=values)
        )
        await self._session.execute(statement)
        return AuthSettings(mode, now, setup_pending)
