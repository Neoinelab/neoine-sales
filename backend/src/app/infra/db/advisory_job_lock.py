"""JobLock Port의 PostgreSQL 세션 advisory lock 구현.

여러 uvicorn 워커 중 한 곳만 작업하게 한다. 세션 잠금은 연결에 붙으므로 전용 연결을 쥐고 있다가
블록이 끝날 때 푼다. 풀에 돌려준 연결에 잠금이 남지 않도록, 해제에 실패하면 연결을 버린다.
"""

import logging
import zlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = logging.getLogger(__name__)

# 상위 32비트는 이 용도의 고정 값('FJOB'), 하위 32비트는 작업 이름의 CRC32(프로세스 간에 같은 값).
_NAMESPACE = 0x464A4F42 << 32


def lock_key(job: str) -> int:
    return _NAMESPACE | zlib.crc32(job.encode())


class PgAdvisoryJobLock:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def try_hold(self, job: str) -> AsyncIterator[bool]:
        key = lock_key(job)
        async with self._engine.connect() as connection:
            held = bool(
                (
                    await connection.execute(
                        text("select pg_try_advisory_lock(:key)"), {"key": key}
                    )
                ).scalar_one()
            )
            try:
                yield held
            finally:
                if held:
                    await self._unlock(connection, key)

    @staticmethod
    async def _unlock(connection: AsyncConnection, key: int) -> None:
        try:
            await connection.execute(text("select pg_advisory_unlock(:key)"), {"key": key})
        except BaseException:  # 취소 포함: 잠금이 풀 연결에 남지 않게 한다
            logger.exception("advisory lock 해제 실패: 연결을 버려 잠금을 푼다")
            await connection.invalidate()
            raise
