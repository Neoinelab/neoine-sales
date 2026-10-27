"""read_only_guard (AC12): 읽기 전용 트랜잭션 + 문장 시간 제한, 끝나면 설정을 되돌린다.

테스트 세션은 바깥 트랜잭션 안의 SAVEPOINT 모드다. 가드는 `begin_nested()`(SAVEPOINT) 안에서
설정하고 항상 롤백해 가드 밖에는 영향이 없어야 한다. 시간 제한은 `pg_sleep`으로 확인한다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.application.ports.report_query_runner import ReportQueryTimeoutError
from app.infra.db.read_only import read_only_guard

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _show(session: AsyncSession, name: str) -> str:
    return str((await session.execute(text(f"SHOW {name}"))).scalar_one())


async def _probe_table(session: AsyncSession) -> None:
    await session.execute(text("CREATE TABLE report_guard_probe (x int)"))


async def test_guard_makes_the_transaction_read_only(session: AsyncSession) -> None:
    async with read_only_guard(session, timeout_ms=5000):
        assert await _show(session, "transaction_read_only") == "on"


async def test_guard_rejects_writes_inside_the_block(session: AsyncSession) -> None:
    await _probe_table(session)

    with pytest.raises(DBAPIError, match="read-only transaction"):
        async with read_only_guard(session, timeout_ms=5000):
            await session.execute(text("INSERT INTO report_guard_probe VALUES (1)"))


async def test_guard_sets_the_statement_timeout_inside_the_block(session: AsyncSession) -> None:
    async with read_only_guard(session, timeout_ms=1234):
        assert await _show(session, "statement_timeout") == "1234ms"


async def test_guard_cancels_statements_over_the_timeout(session: AsyncSession) -> None:
    with pytest.raises(ReportQueryTimeoutError):
        async with read_only_guard(session, timeout_ms=100):
            await session.execute(text("SELECT pg_sleep(1)"))


async def test_settings_are_restored_after_the_guard(session: AsyncSession) -> None:
    await _probe_table(session)
    before_timeout = await _show(session, "statement_timeout")

    async with read_only_guard(session, timeout_ms=1234):
        await session.execute(text("SELECT 1"))

    assert await _show(session, "transaction_read_only") == "off"
    assert await _show(session, "statement_timeout") == before_timeout
    await session.execute(text("INSERT INTO report_guard_probe VALUES (1)"))  # 쓰기가 다시 된다


async def test_session_is_usable_and_writable_after_a_timeout(session: AsyncSession) -> None:
    await _probe_table(session)

    with pytest.raises(ReportQueryTimeoutError):
        async with read_only_guard(session, timeout_ms=100):
            await session.execute(text("SELECT pg_sleep(1)"))

    assert await _show(session, "transaction_read_only") == "off"
    await session.execute(text("INSERT INTO report_guard_probe VALUES (1)"))
    count = (await session.execute(text("SELECT count(*) FROM report_guard_probe"))).scalar_one()
    assert count == 1


async def test_settings_are_restored_after_an_error_in_the_block(session: AsyncSession) -> None:
    class Boom(Exception):  # noqa: N818 - 테스트용 예외
        pass

    with pytest.raises(Boom):
        async with read_only_guard(session, timeout_ms=1234):
            raise Boom

    assert await _show(session, "transaction_read_only") == "off"


async def test_other_database_errors_are_not_reported_as_timeouts(session: AsyncSession) -> None:
    with pytest.raises(DBAPIError):
        async with read_only_guard(session, timeout_ms=5000):
            await session.execute(text("SELECT * FROM no_such_table_for_report_guard"))
