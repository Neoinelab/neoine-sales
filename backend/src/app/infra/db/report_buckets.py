"""날짜·시각 묶음 식(year·quarter·month·ymd)과 업무 시간대 변환.

시각 필드는 서버 업무 오프셋(`ReportContext.utc_offset`)의 달력 날짜로 묶는다.
표시 전용 포맷(weekday·relative·ymd_hm·as_is 등)은 식을 바꾸지 않는다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    ColumnElement,
    Date,
    DateTime,
    Integer,
    cast,
    extract,
    func,
    literal,
    literal_column,
)

from app.domain.report.vocabulary import FieldType, Format

if TYPE_CHECKING:
    from app.domain.report.resolve import ReportContext
    from app.infra.db.report_fields import Expr

_QUARTER_PATTERN: ColumnElement[str] = literal_column("'YYYY \"Q\"Q'")
_MONTH_PATTERN: ColumnElement[str] = literal_column("'YYYY-MM'")
_ONE_SECOND: ColumnElement[object] = literal_column("interval '1 second'")


def local_time(value: Expr, context: ReportContext) -> Expr:
    """timestamptz를 업무 오프셋의 벽시계 시각(timestamp)으로 바꾼다."""
    offset = literal(context.utc_offset.total_seconds()) * _ONE_SECOND
    return func.timezone(offset, value)


def bucket(value: Expr, field_type: FieldType, fmt: Format, context: ReportContext) -> Expr:
    """포맷이 묶음(year·quarter·month·ymd)이면 그 단위의 식, 아니면 원래 식."""
    if fmt is Format.YMD and field_type is FieldType.DATETIME:
        return cast(local_time(value, context), Date)
    if fmt not in {Format.YEAR, Format.QUARTER, Format.MONTH}:
        return value
    local = (
        local_time(value, context) if field_type is FieldType.DATETIME else cast(value, DateTime)
    )
    if fmt is Format.YEAR:
        return cast(extract("year", local), Integer)
    pattern = _QUARTER_PATTERN if fmt is Format.QUARTER else _MONTH_PATTERN
    return func.to_char(local, pattern)
