"""PeriodicTask(docker-compose 계획 AC16·AC20): 즉시 1회, 이후 주기마다. 오류는 격리, 취소는 전파.

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
    runs: list[int] = []

    async def run_once() -> None:
        runs.append(len(runs) + 1)

    sleeper = _Sleeper(stop_after=3)
    task = PeriodicTask(run_once, INTERVAL, name="t", sleep=sleeper)

    with pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    assert runs == [1, 2, 3]
    assert sleeper.calls == [INTERVAL, INTERVAL, INTERVAL]


async def test_first_run_happens_before_any_sleep() -> None:
    order: list[str] = []

    async def run_once() -> None:
        order.append("run")

    async def sleep(seconds: float) -> None:
        order.append("sleep")
        raise asyncio.CancelledError

    task = PeriodicTask(run_once, INTERVAL, name="t", sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    assert order == ["run", "sleep"]


async def test_exception_is_logged_and_loop_continues(caplog: pytest.LogCaptureFixture) -> None:
    runs: list[int] = []

    async def run_once() -> None:
        runs.append(len(runs) + 1)
        if len(runs) == 1:
            msg = "database is down (test double)"
            raise RuntimeError(msg)

    task = PeriodicTask(run_once, INTERVAL, name="forecast-check", sleep=_Sleeper(stop_after=2))

    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    assert runs == [1, 2]
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors
    assert any("forecast-check" in r.getMessage() for r in errors)
    assert any(r.exc_info for r in errors)


async def test_cancellation_inside_run_once_stops_the_loop() -> None:
    runs: list[int] = []

    async def run_once() -> None:
        runs.append(1)
        raise asyncio.CancelledError

    sleeper = _Sleeper(stop_after=99)
    task = PeriodicTask(run_once, INTERVAL, name="t", sleep=sleeper)

    with pytest.raises(asyncio.CancelledError):
        await task.run_forever()

    assert runs == [1]
    assert sleeper.calls == []


async def test_cancelling_the_asyncio_task_ends_it() -> None:
    started = asyncio.Event()

    async def run_once() -> None:
        started.set()

    async def never(seconds: float) -> None:
        await asyncio.Event().wait()

    handle = asyncio.create_task(
        PeriodicTask(run_once, INTERVAL, name="t", sleep=never).run_forever()
    )
    await started.wait()
    handle.cancel()

    with pytest.raises(asyncio.CancelledError):
        await handle
    assert handle.cancelled()


@pytest.mark.parametrize("interval", [0, -1, -0.5])
def test_non_positive_interval_is_rejected(interval: float) -> None:
    async def run_once() -> None:
        return None

    with pytest.raises(ValueError, match=r".+"):
        PeriodicTask(run_once, interval, name="t")
