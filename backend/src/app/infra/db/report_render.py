"""리포트 결과의 표시용 변환: 표시용 SQL 문자열과 결과 값 형 변환."""

from typing import TYPE_CHECKING, cast

from sqlalchemy.dialects import postgresql

from app.domain.report.vocabulary import ResultValueType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Select

    from app.application.ports.report_query_runner import ReportCell

_DECIMAL_PLACES = 2


def display_sql(statement: Select[object]) -> str:
    """사람이 읽는 SQL 문자열(입력한 값이 리터럴로 보인다). 실행에는 쓰지 않는다."""
    compiled = statement.compile(
        dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


def _convert(value: object, value_type: ResultValueType) -> ReportCell:
    if value is None:
        return None
    if value_type is ResultValueType.INTEGER:
        return int(cast("int", value))
    if value_type is ResultValueType.DECIMAL:
        return round(float(cast("float", value)), _DECIMAL_PLACES)
    return cast("ReportCell", value)


def convert_row(
    values: Sequence[object], value_types: Sequence[ResultValueType]
) -> tuple[ReportCell, ...]:
    """DB 값을 컬럼 값 형에 맞춘다: 합계 등 Decimal -> int, 평균 -> 소수 둘째 자리 float."""
    return tuple(_convert(value, kind) for value, kind in zip(values, value_types, strict=True))
