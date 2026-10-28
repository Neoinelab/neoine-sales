"""Reports 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.report.change_report_layout import ChangeReportLayout
from app.application.report.copy_report import CopyReport
from app.application.report.create_report import CreateReport
from app.application.report.delete_report import DeleteReport
from app.application.report.get_report import GetReport
from app.application.report.list_fields import ListReportFields
from app.application.report.list_reports import ListReports
from app.application.report.run_report import RunReport
from app.application.report.run_saved_report import RunSavedReport
from app.application.report.update_report import UpdateReport

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

    def list_reports(self) -> ListReports:
        return ListReports(self._uow)

    def get_report(self) -> GetReport:
        return GetReport(self._uow)

    def create_report(self) -> CreateReport:
        return CreateReport(self._uow, self._clock)

    def update_report(self) -> UpdateReport:
        return UpdateReport(self._uow, self._clock)

    def change_report_layout(self) -> ChangeReportLayout:
        return ChangeReportLayout(self._uow, self._clock)

    def copy_report(self) -> CopyReport:
        return CopyReport(self._uow, self._clock)

    def delete_report(self) -> DeleteReport:
        return DeleteReport(self._uow)

    def run_saved_report(self) -> RunSavedReport:
        return RunSavedReport(self._uow, self._clock)
