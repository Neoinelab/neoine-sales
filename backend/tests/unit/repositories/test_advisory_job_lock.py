"""JobLock 계약(docker-compose 계획 AC18·AC20, 순차 확인만): Fake와 PgAdvisoryJobLock에 같은 기대값.

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
    async with job_lock.try_hold("job-a") as first, job_lock.try_hold("job-a") as second:
        assert first is True
        assert second is False


async def _fail_inside(job_lock: JobLock) -> None:
    async with job_lock.try_hold("job-a"):
        msg = "boom"
        raise RuntimeError(msg)


async def test_lock_is_released_after_the_block(job_lock: JobLock) -> None:
    async with job_lock.try_hold("job-a") as first:
        assert first is True

    async with job_lock.try_hold("job-a") as again:
        assert again is True


async def test_lock_is_released_after_an_error_in_the_block(job_lock: JobLock) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        await _fail_inside(job_lock)

    async with job_lock.try_hold("job-a") as again:
        assert again is True


async def test_failed_attempt_does_not_release_the_holders_lock(job_lock: JobLock) -> None:
    async with job_lock.try_hold("job-a") as first:
        async with job_lock.try_hold("job-a") as second:
            assert second is False
        async with job_lock.try_hold("job-a") as third:  # 첫 보유자는 아직 잡고 있다
            assert first is True
            assert third is False


async def test_different_jobs_do_not_block_each_other(job_lock: JobLock) -> None:
    async with job_lock.try_hold("job-a") as first, job_lock.try_hold("job-b") as other:
        assert first is True
        assert other is True


def test_lock_key_is_stable() -> None:
    expected = (0x464A4F42 << 32) | zlib.crc32(b"forecast-snapshot")

    assert lock_key("forecast-snapshot") == expected
    assert lock_key("forecast-snapshot") == lock_key("forecast-snapshot")
    assert lock_key("a") != lock_key("b")


def test_lock_key_fits_a_signed_bigint() -> None:
    assert 0 <= lock_key("forecast-snapshot") < 2**63


def test_implementations_expose_try_hold() -> None:
    assert hasattr(JobLock, "try_hold")
    assert callable(FakeJobLock.try_hold)
    assert callable(PgAdvisoryJobLock.try_hold)
