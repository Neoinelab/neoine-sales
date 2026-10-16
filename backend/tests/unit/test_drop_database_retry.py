"""임시 DB 삭제 재시도 도우미 단위 테스트(DB 없이 가짜 실행기 사용)."""

import pytest

from tests.support.database import drop_with_retry


class InsufficientPrivilegeError(Exception):
    pass


class ObjectInUseError(Exception):
    pass


class Flaky:
    def __init__(self, failures: int, error: type[Exception] = InsufficientPrivilegeError) -> None:
        self.failures = failures
        self.error = error
        self.calls = 0

    async def __call__(self) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error("permission denied to terminate process")


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


async def test_privilege_error_then_success_returns_attempt_count() -> None:
    execute, sleeps = Flaky(3), Sleeps()

    attempts = await drop_with_retry(execute, sleep=sleeps)

    assert attempts == 4
    assert len(sleeps.delays) == 3


async def test_object_in_use_error_is_retried() -> None:
    execute = Flaky(1, ObjectInUseError)

    assert await drop_with_retry(execute, sleep=Sleeps()) == 2


async def test_first_try_success_does_not_sleep() -> None:
    sleeps = Sleeps()

    assert await drop_with_retry(Flaky(0), sleep=sleeps) == 1
    assert sleeps.delays == []


async def test_persistent_failure_raises_after_max_attempts() -> None:
    execute = Flaky(100)

    with pytest.raises(InsufficientPrivilegeError):
        await drop_with_retry(execute, sleep=Sleeps(), max_attempts=5)

    assert execute.calls == 5


async def test_other_error_is_raised_immediately() -> None:
    execute = Flaky(1, ValueError)

    with pytest.raises(ValueError, match="permission"):
        await drop_with_retry(execute, sleep=Sleeps())

    assert execute.calls == 1


async def test_delays_grow_and_total_stays_within_seconds() -> None:
    sleeps = Sleeps()

    with pytest.raises(InsufficientPrivilegeError):
        await drop_with_retry(Flaky(100), sleep=sleeps)

    assert sleeps.delays == sorted(sleeps.delays)
    assert sleeps.delays[0] == pytest.approx(0.2)
    assert sum(sleeps.delays) < 10
