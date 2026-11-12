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
    """권한 오류가 세 번 난 뒤 성공하면 시도 횟수를 돌려준다."""
    # given: 세 번 실패한 뒤 성공하는 실행기와 기록용 sleep
    execute, sleeps = Flaky(3), Sleeps()

    # when: 재시도하며 삭제한다
    attempts = await drop_with_retry(execute, sleep=sleeps)

    # then: 4번 시도했고 3번 쉬었다
    assert attempts == 4
    assert len(sleeps.delays) == 3


async def test_object_in_use_error_is_retried() -> None:
    """사용 중 오류도 재시도한다."""
    # given: 한 번 사용 중 오류를 내는 실행기
    execute = Flaky(1, ObjectInUseError)

    # when: 재시도하며 삭제한다
    result = await drop_with_retry(execute, sleep=Sleeps())
    # then: 두 번째 시도에서 성공한다
    assert result == 2


async def test_first_try_success_does_not_sleep() -> None:
    """처음에 성공하면 쉬지 않는다."""
    # given: 기록용 sleep
    sleeps = Sleeps()

    # when: 실패 없는 실행기로 삭제한다
    assert await drop_with_retry(Flaky(0), sleep=sleeps) == 1
    # then: 1번 시도했고 쉰 기록이 없다
    assert sleeps.delays == []


async def test_persistent_failure_raises_after_max_attempts() -> None:
    """계속 실패하면 최대 시도 횟수 뒤 예외를 낸다."""
    # given: 계속 실패하는 실행기
    execute = Flaky(100)

    # when·then: 최대 5번까지 재시도하다 권한 오류를 낸다
    with pytest.raises(InsufficientPrivilegeError):
        await drop_with_retry(execute, sleep=Sleeps(), max_attempts=5)

    # then: 5번 호출됐다
    assert execute.calls == 5


async def test_other_error_is_raised_immediately() -> None:
    """다른 종류의 오류는 재시도 없이 바로 낸다."""
    # given: ValueError를 내는 실행기
    execute = Flaky(1, ValueError)

    # when·then: 삭제하면 그 오류가 바로 전파된다
    with pytest.raises(ValueError, match="permission"):
        await drop_with_retry(execute, sleep=Sleeps())

    # then: 한 번만 호출됐다
    assert execute.calls == 1


async def test_delays_grow_and_total_stays_within_seconds() -> None:
    """대기 시간은 늘어나지만 전체는 몇 초 안에 끝난다."""
    # given: 기록용 sleep
    sleeps = Sleeps()

    # when: 계속 실패하는 실행기로 끝까지 재시도한다
    with pytest.raises(InsufficientPrivilegeError):
        await drop_with_retry(Flaky(100), sleep=sleeps)

    # then: 대기 시간이 오름차순이고 첫 대기는 0.2초이며 합계는 10초 미만이다
    assert sleeps.delays == sorted(sleeps.delays)
    assert sleeps.delays[0] == pytest.approx(0.2)
    assert sum(sleeps.delays) < 10
