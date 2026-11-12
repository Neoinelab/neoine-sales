"""원시 SQL 실행 도우미: 스키마 단위 테스트가 임시 DB를 직접 조회·준비할 때 쓴다."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

if TYPE_CHECKING:
    from sqlalchemy.engine import URL


async def run_sql(url: URL, statement: str, params: dict[str, Any] | None = None) -> list[Any]:
    """한 트랜잭션으로 문장을 실행하고 행이 있으면 돌려준다."""
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement), params or {})
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()
