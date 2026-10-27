"""Reports 테스트용 정의 조립 도우미.

원시 입력(`RawReportDefinition`)을 JSON 모양의 dict로 적고, 파싱·해석까지 한 줄로 부른다.
도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이 막히지 않게).

계약(구현 담당이 맞춘다): `RawColumn(field, label, format, prefix_length, group, aggregate)`,
`RawCondition(field, operator, value)`, `RawSort(column, direction)`,
`RawReportDefinition(columns, conditions, combine, sort, row_limit)`는 키워드로 만들 수 있는
frozen dataclass이고 값은 JSON에서 온 그대로(`object`)다. columns·conditions는 tuple이다.
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.report.definition import ReportDefinition
    from app.domain.report.resolve import ReportContext, ResolvedReport

TODAY = date(2026, 10, 27)
SEOUL = timedelta(hours=9)

# 올바른 조건 (필드, 연산자, 값): 검증 통과와 모든 연산자 조합의 SQL 생성 확인에 함께 쓴다
VALID_CONDITIONS: list[tuple[str, str, object]] = [
    ("deal.name", "contains", "abc"),
    ("deal.name", "equals", "ABC"),
    ("deal.name", "starts_with", "ab"),
    ("deal.name", "is_empty", None),
    ("deal.name", "is_not_empty", None),
    ("deal.vendor", "in", [1, 2]),
    ("deal.vendor", "not_in", [3]),
    ("deal.vendor", "is_empty", None),
    ("deal.owner", "in", [1]),
    ("deal.status", "in", ["prospecting", "introduction"]),
    ("deal.forecast_outcome", "not_in", ["lost"]),
    ("deal.risk", "in", ["overdue"]),
    ("deal.bant_budget", "in", [7]),
    ("action.type", "in", [1]),
    ("action.next_action_status", "in", ["open"]),
    ("deal.amount", "eq", 100),
    ("deal.amount", "ne", 0),
    ("deal.amount", "gt", 1),
    ("deal.amount", "gte", 1),
    ("deal.amount", "lt", 1),
    ("deal.amount", "lte", 1),
    ("deal.amount", "between", [1, 10]),
    ("deal.users", "eq", 0),
    ("deal.status_days", "gt", 3),
    ("deal.expected_close", "between", ["2026-01-01", "2026-12-31"]),
    ("deal.expected_close", "before", "2026-10-01"),
    ("deal.expected_close", "after", "2026-10-01"),
    ("deal.expected_close", "relative", {"period": "this_year"}),
    ("deal.created_at", "between", ["2026-01-01", "2026-01-31"]),
    ("deal.created_at", "before", "2026-10-01"),
    ("deal.last_updated_at", "relative", {"period": "last_n_days", "days": 7}),
    ("action.acted_at", "relative", {"period": "this_month"}),
    ("action.due_date", "relative", {"period": "before_today"}),
]


def col(field: str, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """컬럼 JSON. 생략한 값은 API 기본값(null, group=false)이다."""
    return {
        "field": field,
        "label": None,
        "format": None,
        "prefix_length": None,
        "group": False,
        "aggregate": None,
        **overrides,
    }


def cond(field: str, operator: str, value: object = None) -> dict[str, Any]:
    return {"field": field, "operator": operator, "value": value}


def raw(
    columns: Sequence[dict[str, Any]],
    conditions: Sequence[dict[str, Any]] = (),
    *,
    combine: object = "and",
    sort: dict[str, Any] | None = None,
    row_limit: object = 1000,
) -> Any:  # noqa: ANN401 - RawReportDefinition
    from app.domain.report.raw import (  # noqa: PLC0415
        RawColumn,
        RawCondition,
        RawReportDefinition,
        RawSort,
    )

    return RawReportDefinition(
        columns=tuple(RawColumn(**c) for c in columns),
        conditions=tuple(RawCondition(**c) for c in conditions),
        combine=combine,
        sort=None if sort is None else RawSort(**sort),
        row_limit=row_limit,
    )


def parse(
    columns: Sequence[dict[str, Any]],
    conditions: Sequence[dict[str, Any]] = (),
    **top: Any,  # noqa: ANN401
) -> ReportDefinition:
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415

    return parse_report_definition(raw(columns, conditions, **top))


def issues(
    columns: Sequence[dict[str, Any]],
    conditions: Sequence[dict[str, Any]] = (),
    **top: Any,  # noqa: ANN401
) -> list[tuple[tuple[str | int, ...], str]]:
    """위반 목록 [(위치, 코드)]. 정의가 올바르면 AssertionError."""
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415

    try:
        parse(columns, conditions, **top)
    except ReportDefinitionError as error:
        return [(tuple(i.location), i.code) for i in error.issues]
    msg = "정의가 올바른데 위반을 기대했다"
    raise AssertionError(msg)


def context(
    today: date = TODAY, utc_offset: timedelta = SEOUL, stale_days: int = 14
) -> ReportContext:
    from app.domain.deal.risk import RiskBasis  # noqa: PLC0415
    from app.domain.report.resolve import ReportContext  # noqa: PLC0415

    return ReportContext(
        today=today, utc_offset=utc_offset, risk=RiskBasis(today=today, stale_days=stale_days)
    )


def resolved(
    columns: Sequence[dict[str, Any]],
    conditions: Sequence[dict[str, Any]] = (),
    *,
    ctx: ReportContext | None = None,
    **top: Any,  # noqa: ANN401
) -> ResolvedReport:
    from app.domain.report.resolve import resolve_report  # noqa: PLC0415

    return resolve_report(parse(columns, conditions, **top), ctx or context())
