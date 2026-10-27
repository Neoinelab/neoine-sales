"""Reports 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.report.list_fields import ListReportFields
from app.application.report.run_report import RunReport

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ReportUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock

    def list_report_fields(self) -> ListReportFields:
        return ListReportFields()

    def run_report(self) -> RunReport:
        return RunReport(self._uow, self._clock)
