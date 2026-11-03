"""저장용 차트 JSON `chart_to_json`·`chart_from_json` (Reports 4단계 AC7·18).

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
    value_axis_title="금액 (천원)",
    value_min=-0.5,
    value_max=1000,
    secondary_axis=False,
)


def _through_json(chart: Any) -> Any:  # noqa: ANN401 - RawChart
    """실제 저장처럼 JSON 문자열을 한 번 거친다(직렬화 불가한 값이면 여기서 실패한다)."""
    return chart_from_json(json.loads(json.dumps(chart_to_json(chart))))


def test_chart_json_has_the_request_shape_with_all_sixteen_keys() -> None:
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
        "histogram": None,
        "show_total": False,
        "combo_series": None,
    }
    assert len(data) == 16


def test_chart_json_writes_defaults_explicitly() -> None:
    data = chart_to_json(raw_chart("bar", 0, [1]))

    assert data == chart_body("bar", 0)


def test_stored_chart_round_trips_through_json() -> None:
    assert _through_json(FULL) == FULL


@pytest.mark.parametrize("kind", ["bar", "pie", "scatter", "combo", "stacked_100_bar", "area"])
def test_every_kind_round_trips(kind: str) -> None:
    extra: dict[str, Any] = {}
    if kind == "combo":
        # null 계열 설정은 읽을 때 옛 규칙으로 채워지므로, 채운 값으로 왕복한다
        extra["combo_series"] = [combo_item("column"), combo_item("line")]
    chart = raw_chart(kind, 0, [1, 2], legend="none", value_min=0, value_max=100, **extra)

    assert _through_json(chart) == chart


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
    chart = _new_kind_charts()[name]

    assert len(chart_to_json(chart)) == 16
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


# ---- 읽기 호환: 옛 13개 키 저장 형식 (AC4) ----

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
    restored = chart_from_json(_legacy())

    assert (restored.histogram, restored.show_total, restored.combo_series) == (None, False, None)
    assert restored == raw_chart("bar", 0, [1])


def test_legacy_combo_reads_as_column_plus_lines() -> None:
    restored = chart_from_json(_legacy(kind="combo", values=[1, 2, 3], secondary_axis=False))

    assert restored.combo_series == [
        combo_item("column"),
        combo_item("line"),
        combo_item("line"),
    ]


def test_legacy_combo_with_secondary_axis_puts_the_lines_on_the_secondary_axis() -> None:
    restored = chart_from_json(_legacy(kind="combo", values=[1, 2, 3], secondary_axis=True))

    assert restored.combo_series == [
        combo_item("column"),
        combo_item("line", secondary=True),
        combo_item("line", secondary=True),
    ]
    assert restored.secondary_axis is True


def test_combo_with_null_series_settings_reads_as_the_legacy_rule() -> None:
    restored = chart_from_json(_legacy(kind="combo", values=[1, 2], combo_series=None))

    assert restored.combo_series == [combo_item("column"), combo_item("line")]


def test_stored_combo_series_is_kept_as_saved() -> None:
    series = [combo_item("area"), combo_item("column", secondary=True)]

    restored = chart_from_json(
        _legacy(kind="combo", values=[1, 2], secondary_axis=True, combo_series=series)
    )

    assert restored.combo_series == series


@pytest.mark.parametrize("kind", ["bar", "pie", "waterfall"])
def test_non_combo_kinds_keep_no_combo_series_when_reading(kind: str) -> None:
    assert chart_from_json(_legacy(kind=kind)).combo_series is None


@pytest.mark.parametrize("given", ["missing", None])
def test_histogram_without_bins_reads_as_auto(given: object) -> None:
    data = _legacy(kind="histogram", category=None)
    if given is None:
        data["histogram"] = None

    restored = chart_from_json(data)

    assert restored.histogram == AUTO_BINS
    assert restored.category is None


def test_stored_histogram_bins_are_kept_as_saved() -> None:
    given = bins(bin_mode="width", bin_width=2.5, overflow=100)

    restored = chart_from_json(_legacy(kind="histogram", category=None, histogram=given))

    assert restored.histogram == given


def test_null_category_is_accepted_when_reading_regardless_of_kind() -> None:
    # 종류별 판정은 저장할 때 parse_chart가 정의 기준으로 한다(읽을 때는 모양만 본다)
    restored = chart_from_json(_legacy(kind="bar", category=None))

    assert restored.category is None


def test_show_total_is_kept_when_reading() -> None:
    assert chart_from_json(_legacy(kind="waterfall", show_total=True)).show_total is True


def test_broken_new_key_error_has_the_stored_invalid_issue() -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        chart_from_json(_legacy(kind="histogram", category=None, histogram=3))

    assert caught.value.issues == (BROKEN_CHART,)
