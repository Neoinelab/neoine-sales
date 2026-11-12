"""read_only_guard: 읽기 전용 트랜잭션 + 문장 시간 제한, 끝나면 설정을 되돌린다.

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
    """가드 안의 트랜잭션은 읽기 전용이다.

    테스트 코드: RQ-061
    """
    # when: 가드 안에서 트랜잭션 상태를 본다
    async with read_only_guard(session, timeout_ms=5000):
        # then: transaction_read_only가 on이다
        assert await _show(session, "transaction_read_only") == "on"


async def test_guard_rejects_writes_inside_the_block(session: AsyncSession) -> None:
    """가드 안의 쓰기는 읽기 전용 오류로 거절된다.

    테스트 코드: RQ-061
    """
    # given: 쓰기 시험용 테이블
    await _probe_table(session)

    # when·then: 가드 안에서 INSERT하면 read-only transaction 오류가 난다
    with pytest.raises(DBAPIError, match="read-only transaction"):
        async with read_only_guard(session, timeout_ms=5000):
            await session.execute(text("INSERT INTO report_guard_probe VALUES (1)"))


async def test_guard_sets_the_statement_timeout_inside_the_block(session: AsyncSession) -> None:
    """가드 안의 문장 시간 제한은 지정한 값이다.

    테스트 코드: RQ-061
    """
    # when: 1234ms 가드 안에서 시간 제한을 본다
    async with read_only_guard(session, timeout_ms=1234):
        # then: statement_timeout이 1234ms다
        assert await _show(session, "statement_timeout") == "1234ms"


async def test_guard_cancels_statements_over_the_timeout(session: AsyncSession) -> None:
    """시간 제한을 넘기는 문장은 시간 초과 오류로 취소된다.

    테스트 코드: RQ-061
    """
    # when·then: 100ms 가드 안에서 1초 걸리는 문장을 실행하면 ReportQueryTimeoutError가 난다
    with pytest.raises(ReportQueryTimeoutError):
        async with read_only_guard(session, timeout_ms=100):
            await session.execute(text("SELECT pg_sleep(1)"))


async def test_settings_are_restored_after_the_guard(session: AsyncSession) -> None:
    """가드가 끝나면 읽기 전용과 시간 제한이 원래대로 돌아와 쓰기가 된다.

    테스트 코드: RQ-061
    """
    # given: 쓰기 시험용 테이블과 가드 전 시간 제한
    await _probe_table(session)
    before_timeout = await _show(session, "statement_timeout")

    # when: 가드 안에서 읽고 빠져나온다
    async with read_only_guard(session, timeout_ms=1234):
        await session.execute(text("SELECT 1"))

    # then: 읽기 전용이 꺼지고 시간 제한이 원래 값이며 쓰기가 다시 된다
    assert await _show(session, "transaction_read_only") == "off"
    assert await _show(session, "statement_timeout") == before_timeout
    await session.execute(text("INSERT INTO report_guard_probe VALUES (1)"))  # 쓰기가 다시 된다


async def test_session_is_usable_and_writable_after_a_timeout(session: AsyncSession) -> None:
    """시간 초과 뒤에도 세션을 쓸 수 있고 쓰기가 된다.

    테스트 코드: RQ-061
    """
    # given: 쓰기 시험용 테이블
    await _probe_table(session)

    # when·then: 가드 안에서 시간 초과를 일으킨다
    with pytest.raises(ReportQueryTimeoutError):
        async with read_only_guard(session, timeout_ms=100):
            await session.execute(text("SELECT pg_sleep(1)"))

    # then: 읽기 전용이 꺼져 있고 INSERT한 행이 1건이다
    assert await _show(session, "transaction_read_only") == "off"
    await session.execute(text("INSERT INTO report_guard_probe VALUES (1)"))
    count = (await session.execute(text("SELECT count(*) FROM report_guard_probe"))).scalar_one()
    assert count == 1


async def test_settings_are_restored_after_an_error_in_the_block(session: AsyncSession) -> None:
    """가드 안에서 오류가 나도 설정이 원래대로 돌아온다.

    테스트 코드: RQ-061
    """

    # given: 테스트용 예외
    class Boom(Exception):  # noqa: N818 - 테스트용 예외
        pass

    # when·then: 가드 안에서 예외가 나면 그대로 올라온다
    with pytest.raises(Boom):
        async with read_only_guard(session, timeout_ms=1234):
            raise Boom

    # then: 읽기 전용이 꺼져 있다
    assert await _show(session, "transaction_read_only") == "off"


async def test_other_database_errors_are_not_reported_as_timeouts(session: AsyncSession) -> None:
    """시간 초과가 아닌 DB 오류는 시간 초과로 바뀌지 않는다.

    테스트 코드: RQ-061
    """
    # when·then: 없는 테이블을 읽으면 DBAPIError가 그대로 난다
    with pytest.raises(DBAPIError):
        async with read_only_guard(session, timeout_ms=5000):
            await session.execute(text("SELECT * FROM no_such_table_for_report_guard"))
