from datetime import timedelta
from typing import TYPE_CHECKING

from app.application.deal.views import load_thresholds
from app.application.report.views import ReportColumnView, ReportResultView
from app.domain.common.business_date import business_date, business_time
from app.domain.deal.risk import RiskBasis
from app.domain.report.parse import parse_report_definition
from app.domain.report.resolve import ReportContext, resolve_report

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.report.raw import RawReportDefinition


class RunReport:
    """리포트 정의를 검증하고 업무 날짜 기준으로 풀어 읽기 전용으로 실행한다(저장하지 않는다)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, raw: RawReportDefinition) -> ReportResultView:
        definition = parse_report_definition(raw)  # 위반이면 DB를 열기 전에 중단
        now = self._clock.now()
        today = business_date(now)
        offset = business_time(now).utcoffset() or timedelta(0)
        async with self._uow_factory() as uow:
            stale_days = (await load_thresholds(uow)).stale_days
            context = ReportContext(
                today=today,
                utc_offset=offset,
                risk=RiskBasis(today, stale_days),
            )
            result = await uow.reports.run(resolve_report(definition, context))
        return ReportResultView(
            row_scope=definition.row_scope(),
            action_filter=definition.action_filter(),
            deal_numbers_once=definition.deal_numbers_once(),
            columns=tuple(ReportColumnView.of(i, c) for i, c in enumerate(definition.columns)),
            rows=result.rows,
            totals=result.totals,
            total_count=result.total_count,
            truncated=result.total_count > len(result.rows),
            row_limit=definition.row_limit,
            sql=result.sql,
            elapsed_ms=result.elapsed_ms,
            today=today,
        )
