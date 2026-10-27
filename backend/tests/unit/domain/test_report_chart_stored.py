"""저장용 차트 JSON `chart_to_json`·`chart_from_json` (Reports 4단계 AC7·18).

저장 형식은 API 요청과 같은 모양(snake_case, 13개 키 전부)이다. 읽을 때는 모양과 값의 형식만
확인하고(정의 기준 검사는 하지 않는다), 읽을 수 없으면 위치 ("chart",)의 stored-invalid다.
"""

import json
from typing import Any

import pytest
from app.domain.report.stored_chart import BROKEN_CHART, chart_from_json, chart_to_json

from app.domain.report.errors import ReportDefinitionError, ReportIssue
from tests.support.chart_defs import chart_body, raw_chart

FULL = raw_chart(
    "stacked_bar",
    1,
    [2, 3],
    series=0,
    swap=True,
    title="Vendor별 분기 Pipeline",
    legend="right",
    data_labels=True,
    category_axis_title="분기",
    value_axis_title="금액 (천원)",
    value_min=-0.5,
    value_max=1000,
    secondary_axis=False,
)


def _through_json(chart: Any) -> Any:  # noqa: ANN401 - RawChart
    """실제 저장처럼 JSON 문자열을 한 번 거친다(직렬화 불가한 값이면 여기서 실패한다)."""
    return chart_from_json(json.loads(json.dumps(chart_to_json(chart))))


def test_chart_json_has_the_request_shape_with_all_thirteen_keys() -> None:
    data = chart_to_json(FULL)

    assert data == {
        "kind": "stacked_bar",
        "category": 1,
        "series": 0,
        "values": [2, 3],
        "swap": True,
        "title": "Vendor별 분기 Pipeline",
        "legend": "right",
        "data_labels": True,
        "category_axis_title": "분기",
        "value_axis_title": "금액 (천원)",
        "value_min": -0.5,
        "value_max": 1000,
        "secondary_axis": False,
    }


def test_chart_json_writes_defaults_explicitly() -> None:
    data = chart_to_json(raw_chart("bar", 0, [1]))

    assert data == chart_body("bar", 0)


def test_stored_chart_round_trips_through_json() -> None:
    assert _through_json(FULL) == FULL


@pytest.mark.parametrize("kind", ["bar", "pie", "scatter", "combo", "stacked_100_bar", "area"])
def test_every_kind_round_trips(kind: str) -> None:
    chart = raw_chart(kind, 0, [1, 2], legend="none", value_min=0, value_max=100)

    assert _through_json(chart) == chart


def test_round_trip_keeps_numbers_as_numbers() -> None:
    restored = _through_json(raw_chart("line", 0, [1], value_min=0, value_max=2.25))

    assert (restored.value_min, restored.value_max) == (0, 2.25)
    assert isinstance(restored.values, list)


def test_stored_json_without_optional_keys_is_not_required_to_have_them() -> None:
    # 필수 키는 kind·category·values 뿐이다. 선택 키는 읽을 때 기본값이 된다(저장은 항상 13개).
    restored = chart_from_json({"kind": "bar", "category": 0, "values": [1]})

    assert restored == raw_chart("bar", 0, [1])


def test_broken_chart_issue_is_a_stored_invalid_at_chart() -> None:
    expected = ReportIssue(("chart",), "stored-invalid", "저장된 차트 설정을 읽을 수 없습니다.")

    assert expected == BROKEN_CHART


def _base(**changes: object) -> dict[str, Any]:
    return {**chart_body("bar", 0), **changes}


def _without(key: str) -> dict[str, Any]:
    data = _base()
    del data[key]
    return data


@pytest.mark.parametrize(
    "broken",
    [
        [1],
        "text",
        None,
        1,
        {},
        _without("kind"),
        _without("category"),
        _without("values"),
        _base(kind="x"),
        _base(kind="Bar"),
        _base(kind=1),
        _base(category="0"),
        _base(category=None),
        _base(values="1"),
        _base(values=[1, "2"]),
        _base(values=None),
        _base(series="1"),
        _base(swap="no"),
        _base(title=1),
        _base(title=None),
        _base(category_axis_title=1),
        _base(value_axis_title=[]),
        _base(legend="left"),
        _base(legend=1),
        _base(data_labels="yes"),
        _base(secondary_axis=1),
        _base(value_min="1"),
        _base(value_max=True),
    ],
    ids=[
        "array",
        "string",
        "null",
        "number",
        "empty-object",
        "no-kind",
        "no-category",
        "no-values",
        "unknown-kind",
        "kind-case",
        "kind-number",
        "category-string",
        "category-null",
        "values-string",
        "values-mixed",
        "values-null",
        "series-string",
        "swap-string",
        "title-number",
        "title-null",
        "category-title-number",
        "value-title-list",
        "legend-unknown",
        "legend-number",
        "labels-string",
        "secondary-number",
        "min-string",
        "max-bool",
    ],
)
def test_broken_stored_chart_raises_stored_invalid(broken: object) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        chart_from_json(broken)

    (issue,) = caught.value.issues
    assert issue.location == ("chart",)
    assert issue.code == "stored-invalid"
    assert issue.message == "저장된 차트 설정을 읽을 수 없습니다."


def test_reading_does_not_check_the_chart_against_a_definition() -> None:
    # 정의 기준 검사는 저장할 때 서버가 한다. 범주 index가 터무니없어도 모양이 맞으면 읽는다.
    restored = chart_from_json(_base(category=99, values=[98, 99]))

    assert (restored.category, restored.values) == (99, [98, 99])
