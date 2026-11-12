"""JobLock 계약(순차 확인만): Fake와 PgAdvisoryJobLock에 같은 기대값.

경쟁·동시성은 검증하지 않는다. 잡혀 있는 동안 같은 job을 다시 잡으면 False, 블록이 끝나거나
예외가 난 뒤에는 다시 True, 다른 job은 서로 막지 않는다.
"""

import zlib
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.ports.job_lock import JobLock
from app.infra.db.advisory_job_lock import PgAdvisoryJobLock, lock_key
from tests.fakes.job_lock import FakeJobLock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL


@pytest_asyncio.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("sql", id="sql", marks=pytest.mark.integration),
    ]
)
async def job_lock(request: pytest.FixtureRequest) -> AsyncIterator[JobLock]:
    if request.param == "fake":
        yield FakeJobLock()
        return
    url: URL = request.getfixturevalue("test_database_url")
    engine = create_async_engine(url)
    try:
        yield PgAdvisoryJobLock(engine)
    finally:
        await engine.dispose()


async def test_second_holder_gets_false_while_held(job_lock: JobLock) -> None:
    """잡혀 있는 동안 같은 작업을 다시 잡으면 False다

    테스트 코드: FC-043
    """
    # when: 같은 작업 이름을 두 번 잡아 본다
    async with job_lock.try_hold("job-a") as first, job_lock.try_hold("job-a") as second:
        # then: 첫 번째는 True, 두 번째는 기다리지 않고 False다
        assert first is True
        assert second is False


async def _fail_inside(job_lock: JobLock) -> None:
    async with job_lock.try_hold("job-a"):
        msg = "boom"
        raise RuntimeError(msg)


async def test_lock_is_released_after_the_block(job_lock: JobLock) -> None:
    """블록이 끝나면 잠금이 풀린다

    테스트 코드: FC-043
    """
    # given: 한 번 잡았다가 블록을 나간다
    async with job_lock.try_hold("job-a") as first:
        first_acquired = first

    # when: 다시 잡아 본다
    async with job_lock.try_hold("job-a") as again:
        # then: 처음에도 다시도 True다
        assert first_acquired is True
        assert again is True


async def test_lock_is_released_after_an_error_in_the_block(job_lock: JobLock) -> None:
    """블록 안에서 오류가 나도 잠금이 풀린다

    테스트 코드: FC-043
    """
    # when: 블록 안에서 오류를 낸다
    with pytest.raises(RuntimeError, match="boom"):
        await _fail_inside(job_lock)

    # when: 다시 잡아 본다
    async with job_lock.try_hold("job-a") as again:
        # then: True다
        assert again is True


async def test_failed_attempt_does_not_release_the_holders_lock(job_lock: JobLock) -> None:
    """잡지 못한 시도는 보유자의 잠금을 풀지 않는다

    테스트 코드: FC-043
    """
    # given: 첫 보유자가 잡고 있다
    async with job_lock.try_hold("job-a") as first:
        # when: 다른 시도가 실패한 뒤 또 시도한다
        async with job_lock.try_hold("job-a") as second:
            # then: 두 시도 모두 False다 (보유자는 아직 잡고 있다)
            assert second is False
        async with job_lock.try_hold("job-a") as third:  # 첫 보유자는 아직 잡고 있다
            assert first is True
            assert third is False


async def test_different_jobs_do_not_block_each_other(job_lock: JobLock) -> None:
    """다른 작업 이름끼리는 막지 않는다

    테스트 코드: FC-043
    """
    # when: 서로 다른 작업 이름을 잡는다
    async with job_lock.try_hold("job-a") as first, job_lock.try_hold("job-b") as other:
        # then: 둘 다 True다
        assert first is True
        assert other is True


def test_lock_key_is_stable() -> None:
    """잠금 키는 작업 이름으로 정해지고 실행마다 같다

    테스트 코드: FC-043
    """
    # given: 접두사와 crc32로 만든 기대 키
    expected = (0x464A4F42 << 32) | zlib.crc32(b"forecast-snapshot")

    # when: 같은 이름을 두 번, 다른 이름을 각각 계산한다
    key = lock_key("forecast-snapshot")
    again = lock_key("forecast-snapshot")
    key_a = lock_key("a")
    key_b = lock_key("b")

    # then: 기대 키와 같고 반복해도 같으며 다른 이름은 다르다
    assert key == expected
    assert key == again
    assert key_a != key_b


def test_lock_key_fits_a_signed_bigint() -> None:
    """잠금 키는 signed bigint 범위 안이다

    테스트 코드: FC-043
    """
    # when: 잠금 키를 계산한다
    key = lock_key("forecast-snapshot")

    # then: 0 이상 2^63 미만이다
    assert 0 <= key < 2**63


def test_implementations_expose_try_hold() -> None:
    """Port와 두 구현이 try_hold를 가진다"""
    # when: Port와 두 구현의 try_hold를 읽는다
    port_has = hasattr(JobLock, "try_hold")
    fake_try_hold = FakeJobLock.try_hold
    pg_try_hold = PgAdvisoryJobLock.try_hold

    # then: 모두 try_hold를 갖는다
    assert port_has
    assert callable(fake_try_hold)
    assert callable(pg_try_hold)
