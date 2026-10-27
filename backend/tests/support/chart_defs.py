"""Reports 4단계(차트) 테스트용 정의·차트 조립 도우미.

도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이 막히지 않게).

계약(구현 담당이 맞춘다)
- `RawChart`(`app.domain.report.raw`)는 frozen dataclass이고 키워드로 만든다. `kind`·`category`·
  `values`만 필수이고 나머지 기본값은 계획 4.3과 같다. 값은 JSON에서 온 그대로(`object`)이며
  `values`는 **list**다. `chart_from_json`과 `ChartSettings.to_raw()`도 list를 돌려준다.
- 컬럼 index는 정의 `columns` 배열의 위치다.
"""

from typing import TYPE_CHECKING, Any

from tests.support.report_defs import col, raw

if TYPE_CHECKING:
    from app.domain.report.raw import RawChart, RawReportDefinition

GROUP_FIELDS = ("deal.vendor", "deal.status", "deal.owner", "deal.forecast")
VALUE_COLUMNS = (
    {"field": "deal.amount"},
    {"field": "deal.users"},
    {"field": "deal.code", "aggregate": "count"},
)


def chart_definition(groups: int = 1, values: int = 3) -> RawReportDefinition:
    """그룹 컬럼 `groups`개(index 0..groups-1) 다음에 집계 값 컬럼 `values`개가 오는 정의.

    groups=0이면 그룹핑 없는 정의(deal.code, deal.amount)다.
    """
    if groups == 0:
        definition: RawReportDefinition = raw([col("deal.code"), col("deal.amount")])
        return definition
    columns = [col(GROUP_FIELDS[i], group=True) for i in range(groups)]
    columns += [col(**VALUE_COLUMNS[i % len(VALUE_COLUMNS)]) for i in range(values)]
    result: RawReportDefinition = raw(columns)
    return result


_DEFAULT_VALUES: object = object()


def raw_chart(
    kind: object = "bar",
    category: object = 0,
    values: object = _DEFAULT_VALUES,
    **overrides: Any,  # noqa: ANN401 - RawChart 필드를 그대로 덮어쓴다
) -> RawChart:
    """원시 차트. values를 생략하면 [1]이다."""
    from app.domain.report.raw import RawChart  # noqa: PLC0415

    return RawChart(
        kind=kind,
        category=category,
        values=[1] if values is _DEFAULT_VALUES else values,
        **overrides,
    )


def chart_body(kind: str = "bar", category: object = 0, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """API 요청·응답 JSON 모양의 차트(snake_case, 13개 키 전부)."""
    return {
        "kind": kind,
        "category": category,
        "series": None,
        "values": [1],
        "swap": False,
        "title": "",
        "legend": "top",
        "data_labels": False,
        "category_axis_title": "",
        "value_axis_title": "",
        "value_min": None,
        "value_max": None,
        "secondary_axis": False,
        **overrides,
    }


def chart_issues(
    definition: RawReportDefinition, chart: RawChart
) -> list[tuple[tuple[str | int, ...], str]]:
    """차트 위반 목록 [(위치, 코드)]. 차트가 올바르면 AssertionError."""
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415
    from app.domain.report.parse import parse_report_definition  # noqa: PLC0415
    from app.domain.report.parse_chart import parse_chart  # noqa: PLC0415

    try:
        parse_chart(chart, parse_report_definition(definition))
    except ReportDefinitionError as error:
        return [(tuple(i.location), i.code) for i in error.issues]
    msg = "차트가 올바른데 위반을 기대했다"
    raise AssertionError(msg)
