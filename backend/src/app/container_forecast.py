"""Forecast 유스케이스 조립 Container 부분(길이 분리)."""

import logging
from typing import TYPE_CHECKING

from app.application.forecast.ensure_monthly_snapshot import (
    EnsureMonthlyForecastSnapshot,
    SnapshotCheckOutcome,
    SnapshotCheckResult,
)
from app.application.forecast.get_snapshot_summary import GetForecastSnapshotSummary
from app.application.forecast.get_summary import GetForecastSummary
from app.application.forecast.list_snapshots import ListForecastSnapshots
from app.application.forecast.take_snapshot import TakeForecastSnapshot
from app.infra.scheduling.periodic import PeriodicTask

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.job_lock import JobLock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


logger = logging.getLogger(__name__)


def _log_check(result: SnapshotCheckResult) -> SnapshotCheckResult:
    snapshot = result.snapshot
    if result.outcome is SnapshotCheckOutcome.TAKEN and snapshot is not None:
        logger.info(
            "Forecast 스냅숏 저장 완료: period=%s cell_count=%d replaced=%s taken_at=%s",
            snapshot.period,
            snapshot.cell_count,
            snapshot.replaced,
            snapshot.taken_at.isoformat(),
        )
    else:
        logger.debug("Forecast 스냅숏 확인: period=%s outcome=%s", result.period, result.outcome)
    return result


class ForecastUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock
    _job_lock: JobLock
    _snapshot_interval: int

    def get_forecast_summary(self) -> GetForecastSummary:
        return GetForecastSummary(self._uow, self._clock)

    def take_forecast_snapshot(self) -> TakeForecastSnapshot:
        return TakeForecastSnapshot(self._uow, self._clock)

    def list_forecast_snapshots(self) -> ListForecastSnapshots:
        return ListForecastSnapshots(self._uow)

    def get_forecast_snapshot_summary(self) -> GetForecastSnapshotSummary:
        return GetForecastSnapshotSummary(self._uow)

    def ensure_monthly_forecast_snapshot(self) -> EnsureMonthlyForecastSnapshot:
        return EnsureMonthlyForecastSnapshot(
            self._uow, self._clock, self._job_lock, self.take_forecast_snapshot()
        )

    def forecast_snapshot_scheduler(self) -> PeriodicTask:
        """앱 lifespan이 돌리는 주기 실행기(기동 직후 1회, 이후 설정한 간격마다 전월분 확인)."""

        async def check() -> SnapshotCheckResult:
            return _log_check(await self.ensure_monthly_forecast_snapshot().execute())

        return PeriodicTask(check, self._snapshot_interval, name="forecast-snapshot-check")
