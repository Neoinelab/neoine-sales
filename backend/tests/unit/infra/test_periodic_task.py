"""PeriodicTask: 즉시 1회, 이후 주기마다. 오류는 격리, 취소는 전파.

시간은 가짜 sleep으로 주입해 실제로 기다리지 않는다.
"""

import asyncio
import logging

import pytest

from app.infra.scheduling.periodic import PeriodicTask

INTERVAL = 600.0


class _Sleeper:
    """호출 인자를 기록하고 `stop_after`번째 호출에서 CancelledError로 루프를 끝낸다."""

    def __init__(self, stop_after: int) -> None:
        self.calls: list[float] = []
        self._stop_after = stop_after

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if len(self.calls) >= self._stop_after:
            raise asyncio.CancelledError


async def test_runs_once_immediately_then_every_interval() -> None:
    """시작하자마자 한 번 실행하고 이후 간격마다 반복한다

    테스트 코드: FC-044
    """
    # given: 간격 600초와 실행을 기록하는 작업
    runs: list[int] = []

    async def run_once() -> None:
        runs.append(len(runs) + 1)

    sleeper = _Sleeper(stop_after=3)
    task = PeriodicTask(run_once, INTERVAL, name="t", sleep=sleeper)

    # when: 3번째 대기에서 취소될 때까지 실행한다
    with pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    # then: 1·2·3번 실행했고 대기는 매번 간격만큼이다
    assert runs == [1, 2, 3]
    assert sleeper.calls == [INTERVAL, INTERVAL, INTERVAL]


async def test_first_run_happens_before_any_sleep() -> None:
    """첫 실행은 어떤 대기보다 먼저 한다

    테스트 코드: FC-044
    """
    # given: 실행과 대기 순서를 기록하는 작업
    order: list[str] = []

    async def run_once() -> None:
        order.append("run")

    async def sleep(seconds: float) -> None:
        order.append("sleep")
        raise asyncio.CancelledError

    task = PeriodicTask(run_once, INTERVAL, name="t", sleep=sleep)

    # when: 실행기를 돌린다
    with pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    # then: 실행 다음에 대기 순서다
    assert order == ["run", "sleep"]


async def test_exception_is_logged_and_loop_continues(caplog: pytest.LogCaptureFixture) -> None:
    """실행 중 예외는 로그를 남기고 반복을 계속한다

    테스트 코드: FC-044
    """
    # given: 첫 실행에서 예외를 던지는 작업
    runs: list[int] = []

    async def run_once() -> None:
        runs.append(len(runs) + 1)
        if len(runs) == 1:
            msg = "database is down (test double)"
            raise RuntimeError(msg)

    task = PeriodicTask(run_once, INTERVAL, name="forecast-check", sleep=_Sleeper(stop_after=2))

    # when: 두 번째 대기에서 취소될 때까지 실행한다
    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    # then: 두 번 실행했고 실패 로그에 작업 이름과 예외 정보가 있다
    assert runs == [1, 2]
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors
    assert any(
        r.getMessage() == "주기 작업 실패(다음 주기에 다시 시도): forecast-check" for r in errors
    )
    assert any(r.exc_info for r in errors)


async def test_cancellation_inside_run_once_stops_the_loop() -> None:
    """실행 중 취소는 전파되어 루프가 끝난다

    테스트 코드: FC-044
    """
    # given: 실행 중 취소되는 작업
    runs: list[int] = []

    async def run_once() -> None:
        runs.append(1)
        raise asyncio.CancelledError

    sleeper = _Sleeper(stop_after=99)
    task = PeriodicTask(run_once, INTERVAL, name="t", sleep=sleeper)

    # when: 실행기를 돌린다
    with pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    # then: 한 번 실행하고 대기 없이 끝난다
    assert runs == [1]
    assert sleeper.calls == []


async def test_cancelling_the_asyncio_task_ends_it() -> None:
    """asyncio 태스크를 취소하면 끝난다

    테스트 코드: FC-044
    """
    # given: 시작 신호를 보내고 끝없이 대기하는 실행기 태스크
    started = asyncio.Event()

    async def run_once() -> None:
        started.set()

    async def never(seconds: float) -> None:
        await asyncio.Event().wait()

    handle = asyncio.create_task(
        PeriodicTask(run_once, INTERVAL, name="t", sleep=never).run_forever()
    )
    # when: 태스크를 취소한다
    await started.wait()
    handle.cancel()

    with pytest.raises(asyncio.CancelledError):
        await handle
    # then: 취소된 상태로 끝난다
    assert handle.cancelled()


@pytest.mark.parametrize("interval", [0, -1, -0.5])
def test_non_positive_interval_is_rejected(interval: float) -> None:
    """간격이 0 이하이면 ValueError다

    테스트 코드: FC-044
    """

    async def run_once() -> None:
        return None

    # when·then: 0 이하 간격으로 만들면 ValueError다
    with pytest.raises(ValueError, match=r".+"):
        PeriodicTask(run_once, interval, name="t")
