"""EnsureMonthlyForecastSnapshot(docker-compose 계획 AC16~AC20): 전월 스냅숏이 없을 때만 만든다.

기준 월은 서버 OS 로컬 업무 날짜의 전월이다. 잠금(JobLock)을 잡은 한 곳만 확인·저장하고,
못 잡으면 기다리지 않고 건너뛴다. 저장은 `TakeForecastSnapshot`에 맡기므로 여기서는 Fake 대역이
받은 기준 월(호출 여부 포함)과 저장소 상태로 결과를 본다.
"""

from typing import TYPE_CHECKING, Any, cast

import pytest

from app.application.forecast.ensure_monthly_snapshot import (
    FORECAST_SNAPSHOT_JOB,
    EnsureMonthlyForecastSnapshot,
    SnapshotCheckOutcome,
)
from app.application.forecast.take_snapshot import SnapshotResult
from app.domain.forecast.snapshot import YearMonth
from tests.fakes.job_lock import FakeJobLock
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.unit.application.forecast_snapshot_env import cell, local, store_snapshot

if TYPE_CHECKING:
    from datetime import datetime


OCT = YearMonth(2026, 10)


class RecordingTake:
    """TakeForecastSnapshot 대역: 받은 기준 월을 기록하고 실행 결과를 돌려준다."""

    def __init__(self, clock: FixedClock, fail_with: Exception | None = None) -> None:
        self.targets: list[YearMonth | None] = []
        self._clock = clock
        self._fail_with = fail_with

    async def execute(self, target: YearMonth | None = None) -> SnapshotResult:
        self.targets.append(target)
        if self._fail_with is not None:
            raise self._fail_with
        assert target is not None
        return SnapshotResult(target, self._clock.now(), 0, False)


def _build(
    uow: FakeUnitOfWork,
    now: datetime,
    lock: FakeJobLock | None = None,
    fail_with: Exception | None = None,
) -> tuple[EnsureMonthlyForecastSnapshot, RecordingTake, FakeJobLock, FixedClock]:
    clock = FixedClock(now)
    take = RecordingTake(clock, fail_with)
    job_lock = lock or FakeJobLock()
    use_case = EnsureMonthlyForecastSnapshot(
        cast("Any", lambda: uow), clock, job_lock, cast("Any", take)
    )
    return use_case, take, job_lock, clock


async def test_missing_previous_month_is_taken() -> None:
    use_case, take, lock, _ = _build(FakeUnitOfWork(), local(2026, 11, 1, 0, 10))

    result = await use_case.execute()

    assert result.outcome is SnapshotCheckOutcome.TAKEN
    assert result.period == OCT
    assert result.snapshot is not None
    assert result.snapshot.period == OCT
    assert take.targets == [OCT]
    assert lock.acquired == [FORECAST_SNAPSHOT_JOB]


async def test_existing_previous_month_is_left_unchanged() -> None:
    uow = FakeUnitOfWork()
    taken_at = local(2026, 11, 1, 0, 5)
    await store_snapshot(cast("Any", _Env(uow)), OCT, taken_at, cell(2026, 10, amount=7))
    use_case, take, _, _ = _build(uow, local(2026, 11, 20, 9, 0))

    result = await use_case.execute()

    assert result.outcome is SnapshotCheckOutcome.ALREADY_EXISTS
    assert result.period == OCT
    assert result.snapshot is None
    assert take.targets == []
    stored = await uow.forecast_snapshots.get(OCT)
    assert stored is not None
    assert stored.taken_at == taken_at
    assert [(c.tally.count, c.tally.amount) for c in stored.cells] == [(1, 7)]


async def test_lock_held_elsewhere_skips_without_reading_or_taking() -> None:
    uow = FakeUnitOfWork()
    lock = FakeJobLock(held_elsewhere=[FORECAST_SNAPSHOT_JOB])
    use_case, take, _, _ = _build(uow, local(2026, 11, 1, 0, 10), lock)

    result = await use_case.execute()

    assert result.outcome is SnapshotCheckOutcome.LOCKED_ELSEWHERE
    assert result.period == OCT
    assert result.snapshot is None
    assert take.targets == []
    assert await uow.forecast_snapshots.list_periods() == []


async def test_late_start_mid_month_takes_the_previous_month() -> None:
    use_case, take, _, _ = _build(FakeUnitOfWork(), local(2026, 11, 15, 14, 30))

    result = await use_case.execute()

    assert result.outcome is SnapshotCheckOutcome.TAKEN
    assert result.period == OCT
    assert take.targets == [OCT]


async def test_missed_older_months_are_not_backfilled() -> None:
    uow = FakeUnitOfWork()
    use_case, take, _, _ = _build(uow, local(2026, 11, 15))

    await use_case.execute()

    assert take.targets == [OCT]  # 9월 이전은 시도하지 않는다


async def test_january_targets_the_previous_december() -> None:
    use_case, take, _, _ = _build(FakeUnitOfWork(), local(2027, 1, 1, 0, 10))

    result = await use_case.execute()

    assert result.period == YearMonth(2026, 12)
    assert take.targets == [YearMonth(2026, 12)]


async def test_last_evening_of_a_month_still_targets_the_month_before_it() -> None:
    use_case, take, _, _ = _build(FakeUnitOfWork(), local(2026, 10, 31, 23, 59))

    result = await use_case.execute()

    assert result.period == YearMonth(2026, 9)
    assert take.targets == [YearMonth(2026, 9)]


async def test_failure_propagates_and_the_lock_is_released() -> None:
    boom = RuntimeError("database is down (test double)")
    use_case, _, lock, _ = _build(FakeUnitOfWork(), local(2026, 11, 1, 0, 10), fail_with=boom)

    with pytest.raises(RuntimeError, match="database is down"):
        await use_case.execute()

    assert lock.acquired == [FORECAST_SNAPSHOT_JOB]
    assert lock.released == [FORECAST_SNAPSHOT_JOB]


async def test_lock_is_released_after_a_normal_run() -> None:
    use_case, _, lock, _ = _build(FakeUnitOfWork(), local(2026, 11, 1, 0, 10))

    await use_case.execute()

    assert lock.released == [FORECAST_SNAPSHOT_JOB]


async def test_period_is_computed_once_before_locking() -> None:
    uow = FakeUnitOfWork()
    clock = FixedClock(local(2026, 11, 30, 23, 59))
    take = RecordingTake(clock)
    # 잠금을 잡는 사이 시계가 12월로 넘어가도 처음 계산한 기준 월(10월)로 진행한다
    lock = FakeJobLock(on_enter=lambda: clock.advance(120))
    use_case = EnsureMonthlyForecastSnapshot(
        cast("Any", lambda: uow), clock, lock, cast("Any", take)
    )

    result = await use_case.execute()

    assert result.period == OCT
    assert take.targets == [OCT]


class _Env:
    """store_snapshot이 쓰는 최소 환경(저장소만 필요)."""

    def __init__(self, uow: FakeUnitOfWork) -> None:
        self.uow = uow
