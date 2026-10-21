"""Forecast 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.forecast.get_snapshot_summary import GetForecastSnapshotSummary
from app.application.forecast.get_summary import GetForecastSummary
from app.application.forecast.list_snapshots import ListForecastSnapshots
from app.application.forecast.take_snapshot import TakeForecastSnapshot

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ForecastUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock

    def get_forecast_summary(self) -> GetForecastSummary:
        return GetForecastSummary(self._uow, self._clock)

    def take_forecast_snapshot(self) -> TakeForecastSnapshot:
        return TakeForecastSnapshot(self._uow, self._clock)

    def list_forecast_snapshots(self) -> ListForecastSnapshots:
        return ListForecastSnapshots(self._uow)

    def get_forecast_snapshot_summary(self) -> GetForecastSnapshotSummary:
        return GetForecastSnapshotSummary(self._uow)
