from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.common.business_date import business_date
from app.domain.forecast.snapshot import default_snapshot_month

if TYPE_CHECKING:
    from app.application.forecast.take_snapshot import SnapshotResult, TakeForecastSnapshot
    from app.application.ports.clock import Clock
    from app.application.ports.job_lock import JobLock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.forecast.snapshot import YearMonth

FORECAST_SNAPSHOT_JOB = "forecast-snapshot"


class SnapshotCheckOutcome(StrEnum):
    TAKEN = "taken"
    ALREADY_EXISTS = "already-exists"
    LOCKED_ELSEWHERE = "locked-elsewhere"


@dataclass(frozen=True, slots=True)
class SnapshotCheckResult:
    outcome: SnapshotCheckOutcome
    period: YearMonth
    snapshot: SnapshotResult | None = None


class EnsureMonthlyForecastSnapshot:
    """전월 스냅숏이 없을 때만 만든다(잠금을 잡은 한 곳만 실행, 이전 달은 보충 안 함)."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        job_lock: JobLock,
        take: TakeForecastSnapshot,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._job_lock = job_lock
        self._take = take

    async def execute(self) -> SnapshotCheckResult:
        period = default_snapshot_month(business_date(self._clock.now()))
        async with self._job_lock.try_hold(FORECAST_SNAPSHOT_JOB) as held:
            if not held:
                return SnapshotCheckResult(SnapshotCheckOutcome.LOCKED_ELSEWHERE, period)
            async with self._uow_factory() as uow:
                exists = await uow.forecast_snapshots.exists(period)
            if exists:
                return SnapshotCheckResult(SnapshotCheckOutcome.ALREADY_EXISTS, period)
            taken = await self._take.execute(period)
            return SnapshotCheckResult(SnapshotCheckOutcome.TAKEN, period, taken)
