"""테이블별 행 수를 기억해 두었다가 비교하는 step(마이그레이션이 행을 잃지 않았는지 확인)."""

from typing import TYPE_CHECKING

from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.engine import URL


async def given_row_counts(url: URL, tables: Sequence[str]) -> dict[str, list[tuple[int]]]:
    """지금 각 테이블의 행 수를 기억해 둔다."""
    counts: dict[str, list[tuple[int]]] = {}
    for table in tables:
        counts[table] = await run_sql(url, f"select count(*) from {table}")  # noqa: S608
    return counts


async def then_row_counts_are(url: URL, expected: dict[str, list[tuple[int]]]) -> None:
    """각 테이블의 행 수가 기억해 둔 값과 같다."""
    for table, count in expected.items():
        assert await run_sql(url, f"select count(*) from {table}") == count, table  # noqa: S608
