"""저장용 차트 JSON `chart_to_json`·`chart_from_json`: 왕복·읽기 규칙·읽기 호환(RC-R21, RC-R22).

저장 형식은 API 요청과 같은 모양(snake_case, 16개 키 전부)이다. 읽을 때는 모양과 값의 형식만
확인하고(정의 기준 검사는 하지 않는다), 읽을 수 없으면 위치 ("chart",)의 stored-invalid다.
"""

import json
from typing import Any

import pytest

from app.domain.report.errors import ReportDefinitionError, ReportIssue
from app.domain.report.stored_chart import BROKEN_CHART, chart_from_json, chart_to_json
from tests.support.chart_defs import AUTO_BINS, bins, chart_body, combo_item, raw_chart

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
    value_axis_title="금액 (원)",
    value_min=-0.5,
    value_max=1000,
    secondary_axis=False,
)


def _through_json(chart: Any) -> Any:  # noqa: ANN401 - RawChart
    """실제 저장처럼 JSON 문자열을 한 번 거친다(직렬화 불가한 값이면 여기서 실패한다)."""
    return chart_from_json(json.loads(json.dumps(chart_to_json(chart))))


def test_chart_json_has_the_request_shape_with_all_sixteen_keys() -> None:
    """저장 JSON은 요청과 같은 모양의 16키를 모두 가진다."""
    # when: 모든 옵션을 채운 차트를 JSON으로 바꾼다
    data = chart_to_json(FULL)

    # then: 16개 키가 요청 모양(snake_case)으로 모두 있다
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
        "value_axis_title": "금액 (원)",
        "value_min": -0.5,
        "value_max": 1000,
        "secondary_axis": False,
        "histogram": None,
        "show_total": False,
        "combo_series": None,
    }
    assert len(data) == 16


def test_chart_json_writes_defaults_explicitly() -> None:
    """생략한 키도 JSON에는 기본값으로 명시한다."""
    # when: 필수 키만 가진 차트를 JSON으로 바꾼다
    data = chart_to_json(raw_chart("bar", 0, [1]))

    # then: 기본값까지 채운 16키 본문과 같다
    assert data == chart_body("bar", 0)


def test_stored_chart_round_trips_through_json() -> None:
    """모든 옵션을 채운 차트는 JSON을 거쳐도 같은 값으로 돌아온다."""
    # when: 차트를 JSON으로 저장했다 읽는다
    actual = _through_json(FULL)

    # then: 처음 차트와 같다
    assert actual == FULL


@pytest.mark.parametrize("kind", ["bar", "pie", "scatter", "combo", "stacked_100_bar", "area"])
def test_every_kind_round_trips(kind: str) -> None:
    """대표 종류별로 JSON 왕복이 같은 값이다."""
    # given: 종류에 맞는 차트(콤보는 계열 설정을 채워 둔다)
    extra: dict[str, Any] = {}
    if kind == "combo":
        # null 계열 설정은 읽을 때 옛 규칙으로 채워지므로, 채운 값으로 왕복한다
        extra["combo_series"] = [combo_item("column"), combo_item("line")]
    chart = raw_chart(kind, 0, [1, 2], legend="none", value_min=0, value_max=100, **extra)

    # when: JSON으로 저장했다 읽는다
    actual = _through_json(chart)

    # then: 처음 차트와 같다
    assert actual == chart


def _new_kind_charts() -> dict[str, Any]:
    return {
        "stacked_horizontal_bar": raw_chart("stacked_horizontal_bar", 0, [1, 2], swap=True),
        "bubble": raw_chart("bubble", 0, [1, 2, 3], value_min=0),
        "treemap": raw_chart("treemap", 0, [1], series=2),
        "histogram": raw_chart(
            "histogram", None, [1], histogram=bins(bin_mode="count", bin_count=5)
        ),
        "waterfall": raw_chart("waterfall", 0, [1], show_total=True),
        "combo": raw_chart(
            "combo",
            0,
            [1, 2],
            secondary_axis=True,
            combo_series=[combo_item("stacked_area"), combo_item("line_markers", secondary=True)],
        ),
    }


@pytest.mark.parametrize(
    "name", ["stacked_horizontal_bar", "bubble", "treemap", "histogram", "waterfall", "combo"]
)
def test_chart_to_json_writes_sixteen_keys_and_round_trips(name: str) -> None:
    """새 종류(전용 옵션 포함)도 16키로 쓰고 왕복해도 같다."""
    # given: 새 종류 차트
    chart = _new_kind_charts()[name]

    # when: JSON으로 바꾸고 저장했다 읽는다
    data = chart_to_json(chart)
    restored = _through_json(chart)

    # then: 16키이고 처음 차트와 같다
    assert len(data) == 16
    assert restored == chart


def test_round_trip_keeps_numbers_as_numbers() -> None:
    """범위 숫자와 값 목록의 타입이 왕복 뒤에도 그대로다."""
    # when: 범위를 가진 꺾은선을 JSON으로 저장했다 읽는다
    restored = _through_json(raw_chart("line", 0, [1], value_min=0, value_max=2.25))

    # then: 범위가 숫자이고 값은 list다
    assert (restored.value_min, restored.value_max) == (0, 2.25)
    assert isinstance(restored.values, list)


def test_stored_json_without_optional_keys_is_not_required_to_have_them() -> None:
    """필수 키(kind·category·values)만 있어도 읽고 선택 키는 기본값이 된다.

    테스트 코드: RC-043
    """
    # when: 필수 키 세 개만 있는 JSON을 읽는다
    # 필수 키는 kind·category·values 뿐이다. 선택 키는 읽을 때 기본값이 된다(저장은 항상 13개).
    restored = chart_from_json({"kind": "bar", "category": 0, "values": [1]})

    # then: 기본값으로 채운 차트와 같다
    assert restored == raw_chart("bar", 0, [1])


def test_broken_chart_issue_is_a_stored_invalid_at_chart() -> None:
    """깨진 차트의 위반 상수는 `chart` 위치의 stored-invalid다.

    테스트 코드: RC-039
    """
    # given: `["chart"]` 위치의 stored-invalid 위반
    expected = ReportIssue(("chart",), "stored-invalid", "저장된 차트 설정을 읽을 수 없습니다.")

    # when: 읽기 실패에 쓰는 BROKEN_CHART 상수를 읽는다
    actual = BROKEN_CHART
    # then: 위 위반과 같다
    assert expected == actual


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
        _base(histogram=3),
        _base(histogram=[]),
        _base(histogram={**AUTO_BINS, "bin_mode": 1}),
        _base(histogram={**AUTO_BINS, "bin_count": "5"}),
        _base(histogram={**AUTO_BINS, "bin_width": "x"}),
        _base(histogram={**AUTO_BINS, "overflow": True}),
        _base(histogram={**AUTO_BINS, "underflow": "1"}),
        _base(show_total="x"),
        _base(show_total=1),
        _base(combo_series=[1]),
        _base(combo_series="line"),
        _base(combo_series=[{"type": 1, "secondary": False}]),
        _base(combo_series=[{"type": "line", "secondary": "no"}]),
        _base(combo_series=[{"type": "line"}]),
        _base(kind="histogram", histogram={**AUTO_BINS, "bin_mode": "foo"}),
        _base(kind="histogram", histogram={**AUTO_BINS, "bin_mode": "AUTO"}),
        _base(combo_series=[{"type": "pie", "secondary": False}]),
        _base(combo_series=[{"type": "Line", "secondary": False}]),
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
        "histogram-number",
        "histogram-list",
        "histogram-mode-number",
        "histogram-count-string",
        "histogram-width-string",
        "histogram-overflow-bool",
        "histogram-underflow-string",
        "show-total-string",
        "show-total-number",
        "combo-series-item-number",
        "combo-series-string",
        "combo-series-type-number",
        "combo-series-secondary-string",
        "combo-series-no-secondary",
        "histogram-mode-unknown",
        "histogram-mode-case",
        "combo-series-type-unknown",
        "combo-series-type-case",
    ],
)
def test_broken_stored_chart_raises_stored_invalid(broken: object) -> None:
    """읽기 규칙에 어긋난 저장 차트는 stored-invalid로 거절한다.

    테스트 코드: RC-039
    """
    # when·then: 어긋난 JSON을 읽으면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        chart_from_json(broken)

    # then: 위반은 `["chart"]` 위치 stored-invalid 하나이고 문구는 "저장된 차트 설정을 읽을 수
    #   없습니다."다
    (issue,) = caught.value.issues
    assert issue.location == ("chart",)
    assert issue.code == "stored-invalid"
    assert issue.message == "저장된 차트 설정을 읽을 수 없습니다."


def test_reading_does_not_check_the_chart_against_a_definition() -> None:
    """저장 차트를 읽을 때는 정의와 맞는지 보지 않는다.

    테스트 코드: RC-042
    """
    # when: 터무니없는 범주·값 index를 가진 JSON을 읽는다
    # 정의 기준 검사는 저장할 때 서버가 한다. 범주 index가 터무니없어도 모양이 맞으면 읽는다.
    restored = chart_from_json(_base(category=99, values=[98, 99]))

    # then: 모양이 맞으면 그대로 읽힌다
    assert (restored.category, restored.values) == (99, [98, 99])


LEGACY_KEYS = [
    "kind",
    "category",
    "series",
    "values",
    "swap",
    "title",
    "legend",
    "data_labels",
    "category_axis_title",
    "value_axis_title",
    "value_min",
    "value_max",
    "secondary_axis",
]


def _legacy(**changes: object) -> dict[str, Any]:
    """새 키 3개가 없는 옛 저장 JSON."""
    data = {k: v for k, v in chart_body("bar", 0).items() if k in LEGACY_KEYS}
    return {**data, **changes}


def test_legacy_thirteen_key_chart_reads_with_defaults() -> None:
    """새 키 세 개가 없는 옛 13키 차트는 새 키 기본값으로 읽힌다.

    테스트 코드: RC-043
    """
    # when: 옛 13키 JSON을 읽는다
    restored = chart_from_json(_legacy())

    # then: 구간 null, 합계 false, 계열 설정 null이고 나머지는 그대로다
    assert (restored.histogram, restored.show_total, restored.combo_series) == (None, False, None)
    assert restored == raw_chart("bar", 0, [1])


def test_legacy_combo_reads_as_column_plus_lines() -> None:
    """계열 설정이 없는 옛 콤보는 첫 값 막대·나머지 꺾은선으로 읽힌다.

    테스트 코드: RC-044
    """
    # when: 보조 축이 꺼진 옛 콤보 JSON을 읽는다
    restored = chart_from_json(_legacy(kind="combo", values=[1, 2, 3], secondary_axis=False))

    # then: 첫 값은 묶은 세로 막대, 나머지는 기본 축 꺾은선이다
    assert restored.combo_series == [
        combo_item("column"),
        combo_item("line"),
        combo_item("line"),
    ]


def test_legacy_combo_with_secondary_axis_puts_the_lines_on_the_secondary_axis() -> None:
    """보조 축이 켜진 옛 콤보는 꺾은선이 보조 축으로 읽힌다.

    테스트 코드: RC-044
    """
    # when: 보조 축이 켜진 옛 콤보 JSON을 읽는다
    restored = chart_from_json(_legacy(kind="combo", values=[1, 2, 3], secondary_axis=True))

    # then: 꺾은선이 보조 축이고 secondary_axis가 켜져 있다
    assert restored.combo_series == [
        combo_item("column"),
        combo_item("line", secondary=True),
        combo_item("line", secondary=True),
    ]
    assert restored.secondary_axis is True


def test_combo_with_null_series_settings_reads_as_the_legacy_rule() -> None:
    """계열 설정이 null인 콤보도 옛 규칙으로 읽힌다.

    테스트 코드: RC-044
    """
    # when: 계열 설정이 null인 콤보 JSON을 읽는다
    restored = chart_from_json(_legacy(kind="combo", values=[1, 2], combo_series=None))

    # then: 막대와 꺾은선이다
    assert restored.combo_series == [combo_item("column"), combo_item("line")]


def test_stored_combo_series_is_kept_as_saved() -> None:
    """저장된 콤보 계열 설정은 그대로 읽힌다.

    테스트 코드: RC-045
    """
    # given: 종류와 보조 축이 지정된 계열 설정
    series = [combo_item("area"), combo_item("column", secondary=True)]

    # when: 그 설정을 가진 콤보 JSON을 읽는다
    restored = chart_from_json(
        _legacy(kind="combo", values=[1, 2], secondary_axis=True, combo_series=series)
    )

    # then: 계열 설정이 저장된 그대로다
    assert restored.combo_series == series


@pytest.mark.parametrize("kind", ["bar", "pie", "waterfall"])
def test_non_combo_kinds_keep_no_combo_series_when_reading(kind: str) -> None:
    """콤보가 아닌 종류는 읽어도 계열 설정이 없다.

    테스트 코드: RC-044
    """
    # when: 콤보가 아닌 옛 JSON을 읽는다
    actual = chart_from_json(_legacy(kind=kind)).combo_series

    # then: 계열 설정이 null이다
    assert actual is None


@pytest.mark.parametrize("given", ["missing", None])
def test_histogram_without_bins_reads_as_auto(given: object) -> None:
    """구간이 없거나 null인 저장 히스토그램은 자동 구간으로 읽힌다.

    테스트 코드: RC-045
    """
    # given: 구간 키가 없는(또는 null인) 히스토그램 JSON
    data = _legacy(kind="histogram", category=None)
    if given is None:
        data["histogram"] = None

    # when: JSON을 읽는다
    restored = chart_from_json(data)

    # then: 구간은 auto 5키이고 범주는 null이다
    assert restored.histogram == AUTO_BINS
    assert restored.category is None


def test_stored_histogram_bins_are_kept_as_saved() -> None:
    """저장된 구간 설정은 그대로 읽힌다.

    테스트 코드: RC-045
    """
    # given: 너비 방식과 오버플로가 있는 구간 설정
    given = bins(bin_mode="width", bin_width=2.5, overflow=100)

    # when: 그 설정을 가진 히스토그램 JSON을 읽는다
    restored = chart_from_json(_legacy(kind="histogram", category=None, histogram=given))

    # then: 구간 설정이 저장된 그대로다
    assert restored.histogram == given


def test_null_category_is_accepted_when_reading_regardless_of_kind() -> None:
    """읽을 때는 종류와 무관하게 null 범주를 받는다.

    테스트 코드: RC-045
    """
    # when: 범주가 null인 막대 JSON을 읽는다 (종류별 판정은 저장할 때 정의 기준으로 한다)
    # 종류별 판정은 저장할 때 parse_chart가 정의 기준으로 한다(읽을 때는 모양만 본다)
    restored = chart_from_json(_legacy(kind="bar", category=None))

    # then: 범주가 null로 읽힌다
    assert restored.category is None


def test_show_total_is_kept_when_reading() -> None:
    """저장된 합계 막대 켜기는 그대로 읽힌다.

    테스트 코드: RC-045
    """
    # when: 합계 막대를 켠 폭포 JSON을 읽는다
    actual = chart_from_json(_legacy(kind="waterfall", show_total=True)).show_total

    # then: show_total이 true다
    assert actual is True


def test_broken_new_key_error_has_the_stored_invalid_issue() -> None:
    """새 키(구간)가 깨진 JSON도 stored-invalid 위반으로 거절한다.

    테스트 코드: RC-039
    """
    # when·then: 구간이 숫자인 히스토그램 JSON을 읽으면 ReportDefinitionError가 난다
    with pytest.raises(ReportDefinitionError) as caught:
        chart_from_json(_legacy(kind="histogram", category=None, histogram=3))

    # then: 위반은 깨진 차트 상수 하나다
    assert caught.value.issues == (BROKEN_CHART,)
