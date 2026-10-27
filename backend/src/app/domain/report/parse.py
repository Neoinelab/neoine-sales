"""원시 리포트 정의를 검증해 `ReportDefinition`으로 만든다. 위반을 모두 모아 한 번에 알린다."""

from typing import TYPE_CHECKING

from app.domain.report.definition import ReportDefinition, ReportSort
from app.domain.report.errors import IssueLog, ReportDefinitionError
from app.domain.report.parse_columns import enum_member, parse_columns
from app.domain.report.parse_conditions import parse_conditions
from app.domain.report.vocabulary import DEFAULT_ROW_LIMIT, ROW_LIMITS, Combine, SortDirection

if TYPE_CHECKING:
    from app.domain.report.raw import RawReportDefinition, RawSort


def parse_report_definition(raw: RawReportDefinition) -> ReportDefinition:
    """허용 필드·포맷·연산자·집계·값·한도를 검사한다. 위반이 있으면 `ReportDefinitionError`."""
    log = IssueLog()
    columns = parse_columns(raw.columns, log)
    conditions = parse_conditions(raw.conditions, log)
    combine = _combine(raw.combine, log)
    sort = _sort(raw.sort, len(raw.columns), log)
    row_limit = _row_limit(raw.row_limit, log)
    if log.items:
        raise ReportDefinitionError(log.items)
    return ReportDefinition(columns, conditions, combine, sort, row_limit)


def _combine(raw: object, log: IssueLog) -> Combine:
    combine = enum_member(Combine, raw)
    if combine is None:
        log.add(("combine",), "combine-invalid", "조건 결합은 and 또는 or만 쓸 수 있습니다")
        return Combine.AND
    return combine


def _sort(raw: RawSort | None, column_count: int, log: IssueLog) -> ReportSort | None:
    if raw is None:
        return None
    direction = enum_member(SortDirection, raw.direction)
    column = raw.column
    valid_column = type(column) is int and 0 <= column < column_count
    if not valid_column:
        log.add(("sort", "column"), "sort-invalid", "정렬 기준은 컬럼 위치(0부터)여야 합니다")
    if direction is None:
        log.add(("sort", "direction"), "sort-invalid", "정렬 방향은 asc 또는 desc만 쓸 수 있습니다")
    if not valid_column or direction is None or type(column) is not int:
        return None
    return ReportSort(column, direction)


def _row_limit(raw: object, log: IssueLog) -> int:
    if type(raw) is not int or raw not in ROW_LIMITS:
        names = ", ".join(str(n) for n in ROW_LIMITS)
        log.add(("row_limit",), "row-limit-invalid", f"행 수 제한은 {names} 중 하나여야 합니다")
        return DEFAULT_ROW_LIMIT
    return raw
