"""Dashboard 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.dashboard.get_summary import GetDashboardSummary

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class DashboardUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock

    def get_dashboard_summary(self) -> GetDashboardSummary:
        return GetDashboardSummary(self._uow, self._clock)
