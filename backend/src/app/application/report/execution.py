"""리포트 실행·저장이 함께 쓰는 조립: 업무 날짜 기준, 결과 보기, 저장할 내용."""

from datetime import timedelta
from typing import TYPE_CHECKING

from app.application.deal.views import load_thresholds
from app.application.report.views import ReportColumnView, ReportResultView
from app.domain.common.business_date import business_date, business_time
from app.domain.deal.risk import RiskBasis
from app.domain.report.parse import parse_report_definition
from app.domain.report.resolve import ReportContext, resolve_report
from app.domain.saved_report.values import (
    ReportContent,
    ReportVisibility,
    normalize_report_description,
    normalize_report_name,
)

if TYPE_CHECKING:
    from datetime import date, datetime

    from app.application.ports.report_query_runner import ReportRows
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.report.definition import ReportDefinition
    from app.domain.report.raw import RawReportDefinition


async def report_context(uow: UnitOfWork, now: datetime) -> ReportContext:
    """업무 날짜와 SQL 날짜 변환용 오프셋, 경고 판정 기준."""
    today = business_date(now)
    offset = business_time(now).utcoffset() or timedelta(0)
    stale_days = (await load_thresholds(uow)).stale_days
    return ReportContext(today=today, utc_offset=offset, risk=RiskBasis(today, stale_days))


def result_view(definition: ReportDefinition, rows: ReportRows, today: date) -> ReportResultView:
    return ReportResultView(
        row_scope=definition.row_scope(),
        action_filter=definition.action_filter(),
        deal_numbers_once=definition.deal_numbers_once(),
        columns=tuple(ReportColumnView.of(i, c) for i, c in enumerate(definition.columns)),
        rows=rows.rows,
        totals=rows.totals,
        total_count=rows.total_count,
        truncated=rows.total_count > len(rows.rows),
        row_limit=definition.row_limit,
        sql=rows.sql,
        elapsed_ms=rows.elapsed_ms,
        today=today,
    )


async def prepare_content(  # noqa: PLR0913 - 저장 내용에 필요한 값이 모두 다르다
    uow: UnitOfWork,
    now: datetime,
    *,
    name: str,
    description: str,
    visibility: str,
    definition: RawReportDefinition,
) -> ReportContent:
    """이름·설명·공개 범위를 정규화하고 정의를 검증해, 서버가 만든 SQL과 함께 저장 내용으로 묶는다.

    이름 등 메타 오류가 있으면 그것만 먼저 알린다(정의 검증·SQL 생성 전).
    """
    clean_name = normalize_report_name(name)
    clean_description = normalize_report_description(description)
    parsed_visibility = ReportVisibility.parse(visibility)
    parsed = parse_report_definition(definition)
    context = await report_context(uow, now)
    sql = uow.reports.render_sql(resolve_report(parsed, context))
    return ReportContent(clean_name, clean_description, parsed_visibility, definition, sql)
