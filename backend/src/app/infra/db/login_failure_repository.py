"""LoginFailureRepository Port의 SQLAlchemy 구현."""

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.domain.auth.login_failure import FailureCounter
from app.infra.db.models_auth import LoginFailureRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlLoginFailureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_update(self, key: str) -> FailureCounter | None:
        # 행이 아직 없어도 같은 키의 트랜잭션을 직렬화하도록 키 단위 advisory lock을 먼저 잡는다.
        lock = func.pg_advisory_xact_lock(func.hashtextextended(key, 0))
        await self._session.execute(select(lock))
        statement = (
            select(LoginFailureRow)
            .where(LoginFailureRow.key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = (await self._session.scalars(statement)).one_or_none()
        if row is None:
            return None
        return FailureCounter(
            key=row.key,
            failures=row.failures,
            window_started_at=row.window_started_at,
            locked_until=row.locked_until,
        )

    async def save(self, counter: FailureCounter) -> None:
        values = {
            "failures": counter.failures,
            "window_started_at": counter.window_started_at,
            "locked_until": counter.locked_until,
        }
        statement = insert(LoginFailureRow).values(key=counter.key, **values)
        await self._session.execute(
            statement.on_conflict_do_update(index_elements=["key"], set_=values),
            execution_options={"populate_existing": True},
        )

    async def delete(self, key: str) -> None:
        await self._session.execute(delete(LoginFailureRow).where(LoginFailureRow.key == key))
