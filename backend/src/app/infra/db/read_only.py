"""리포트 조회용 읽기 전용 가드: SAVEPOINT 안에서 READ ONLY + 문장 시간 제한을 걸고 항상 되돌린다.

운영(새 세션)과 테스트(바깥 트랜잭션을 롤백하는 세션)에서 같은 코드로 동작하며, 가드 밖의 쓰기와
설정에는 영향이 없다. 시간 제한 초과(SQLSTATE 57014)는 `ReportQueryTimeoutError`로 바꾼다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.application.ports.report_query_runner import ReportQueryTimeoutError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

QUERY_CANCELED = "57014"


def _is_timeout(error: DBAPIError) -> bool:
    origin = error.orig
    code = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    return code == QUERY_CANCELED


@asynccontextmanager
async def read_only_guard(session: AsyncSession, timeout_ms: int) -> AsyncIterator[None]:
    """블록 안의 문장은 읽기 전용이고 `timeout_ms`를 넘으면 취소된다(숫자는 코드 상수만 쓴다)."""
    limit = int(timeout_ms)
    savepoint = await session.begin_nested()
    try:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        await session.execute(text(f"SET LOCAL statement_timeout = {limit}"))
        yield
    except DBAPIError as error:
        if _is_timeout(error):
            raise ReportQueryTimeoutError from error
        raise
    finally:
        if savepoint.is_active:
            await savepoint.rollback()
