"""원시 리포트 정의를 검증해 `ReportDefinition`으로 만든다. 위반을 모두 모아 한 번에 알린다."""

from typing import TYPE_CHECKING

from app.domain.report.definition import ReportDefinition
from app.domain.report.errors import IssueLog, ReportDefinitionError
from app.domain.report.parse_columns import enum_member, parse_columns
from app.domain.report.parse_conditions import parse_conditions
from app.domain.report.vocabulary import DEFAULT_ROW_LIMIT, ROW_LIMITS, Combine

if TYPE_CHECKING:
    from app.domain.report.raw import RawReportDefinition


def parse_report_definition(raw: RawReportDefinition) -> ReportDefinition:
    """허용 필드·포맷·연산자·집계·값·한도를 검사한다. 위반이 있으면 `ReportDefinitionError`."""
    log = IssueLog()
    columns = parse_columns(raw.columns, log)
    conditions = parse_conditions(raw.conditions, log)
    combine = _combine(raw.combine, log)
    row_limit = _row_limit(raw.row_limit, log)
    if log.items:
        raise ReportDefinitionError(log.items)
    return ReportDefinition(columns, conditions, combine, row_limit)


def _combine(raw: object, log: IssueLog) -> Combine:
    combine = enum_member(Combine, raw)
    if combine is None:
        log.add(("combine",), "combine-invalid", "조건 결합은 and 또는 or만 쓸 수 있습니다")
        return Combine.AND
    return combine


def _row_limit(raw: object, log: IssueLog) -> int:
    if type(raw) is not int or raw not in ROW_LIMITS:
        names = ", ".join(str(n) for n in ROW_LIMITS)
        log.add(("row_limit",), "row-limit-invalid", f"행 수 제한은 {names} 중 하나여야 합니다")
        return DEFAULT_ROW_LIMIT
    return raw
