"""차트 옵션 3개의 검증 (Excel 확장 AC3·10·12·14): histogram·show_total·combo_series.

위치는 `("chart", "<옵션>", ...)`이고, 허용하지 않는 종류에서 쓰면 chart-option-invalid다.
정규화된 값은 `ChartSettings.to_raw()`로 확인한다(JSON에 그대로 쓰는 dict·list).
"""

from typing import Any

import pytest

from app.domain.report.errors import ReportDefinitionError
from app.domain.report.parse import parse_report_definition
from app.domain.report.parse_chart import parse_chart
from tests.support.chart_defs import (
    AUTO_BINS,
    bins,
    chart_definition,
    chart_issues,
    combo_item,
    raw_chart,
)

ONE = chart_definition(1, 11)  # 0 = 그룹, 1..11 = 집계 값
LOC_HIST = ("chart", "histogram")
SAFE = 2**53 - 1


def _hist(histogram: Any) -> Any:  # noqa: ANN401 - RawChart
    return raw_chart("histogram", None, [1], histogram=histogram)


def _combo(series: Any, values: list[int] | None = None, **overrides: Any) -> Any:  # noqa: ANN401
    return raw_chart("combo", 0, values or [1, 2], combo_series=series, **overrides)


def _raw_of(chart: Any, definition: Any = ONE) -> Any:  # noqa: ANN401
    return parse_chart(chart, parse_report_definition(definition)).to_raw()


def _issues(chart: Any) -> list[tuple[Any, str]]:  # noqa: ANN401
    return chart_issues(ONE, chart)


def _messages(chart: Any) -> list[str]:  # noqa: ANN401
    with pytest.raises(ReportDefinitionError) as caught:
        _raw_of(chart)
    return [i.message for i in caught.value.issues]


# ---- 히스토그램: 정규화 ----


@pytest.mark.parametrize("given", [None, AUTO_BINS])
def test_histogram_without_bins_is_normalized_to_auto(given: object) -> None:
    assert _raw_of(_hist(given)).histogram == AUTO_BINS


def test_histogram_keeps_a_valid_bin_setting() -> None:
    given = bins(bin_mode="count", bin_count=8, overflow=100.5, underflow=-10)

    assert _raw_of(_hist(given)).histogram == given


def test_histogram_width_mode_keeps_width() -> None:
    given = bins(bin_mode="width", bin_width=2.5)

    assert _raw_of(_hist(given)).histogram == given


# ---- 히스토그램: 구간 수 ----


@pytest.mark.parametrize("count", [1, 100])
def test_histogram_count_mode_accepts_1_and_100(count: int) -> None:
    given = bins(bin_mode="count", bin_count=count)

    assert _raw_of(_hist(given)).histogram["bin_count"] == count


@pytest.mark.parametrize("count", [0, 101, -1, 2.5, "3", True, None])
def test_histogram_count_mode_rejects_out_of_range_and_non_integers(count: object) -> None:
    found = _issues(_hist(bins(bin_mode="count", bin_count=count)))

    assert found == [(("chart", "histogram", "bin_count"), "chart-histogram-invalid")]


def test_histogram_count_message_is_in_korean() -> None:
    messages = _messages(_hist(bins(bin_mode="count", bin_count=0)))

    assert messages == ["구간 수는 1~100의 정수입니다"]


# ---- 히스토그램: 구간 너비 ----


@pytest.mark.parametrize("width", [0.5, 1, SAFE])
def test_histogram_width_mode_accepts_positive_finite_widths(width: float) -> None:
    given = bins(bin_mode="width", bin_width=width)

    assert _raw_of(_hist(given)).histogram["bin_width"] == width


@pytest.mark.parametrize(
    "width", [0, 0.0, -1, float("inf"), float("-inf"), float("nan"), SAFE + 1, True, "1", None]
)
def test_histogram_width_mode_rejects_zero_negative_and_non_finite(width: object) -> None:
    found = _issues(_hist(bins(bin_mode="width", bin_width=width)))

    assert found == [(("chart", "histogram", "bin_width"), "chart-histogram-invalid")]


def test_histogram_width_message_is_in_korean() -> None:
    messages = _messages(_hist(bins(bin_mode="width", bin_width=0)))

    assert messages == ["구간 너비는 0보다 큰 숫자입니다"]


# ---- 히스토그램: 쓰지 않는 칸은 비워 둔다 ----


@pytest.mark.parametrize(
    ("given", "key"),
    [
        (bins(bin_mode="auto", bin_count=5), "bin_count"),
        (bins(bin_mode="auto", bin_width=5), "bin_width"),
        (bins(bin_mode="count", bin_count=5, bin_width=5), "bin_width"),
        (bins(bin_mode="width", bin_width=5, bin_count=5), "bin_count"),
    ],
)
def test_histogram_mode_requires_unused_fields_null(given: dict[str, Any], key: str) -> None:
    found = _issues(_hist(given))

    assert found == [(("chart", "histogram", key), "chart-histogram-invalid")]


def test_histogram_unused_field_message_is_in_korean() -> None:
    assert _messages(_hist(bins(bin_mode="auto", bin_count=5))) == [
        "이 구간 방식에서는 비워 두세요"
    ]


# ---- 히스토그램: 모양과 방식 ----


@pytest.mark.parametrize("mode", ["log", "AUTO", "", None, 1, True])
def test_histogram_unknown_mode_is_rejected_at_bin_mode(mode: object) -> None:
    found = _issues(_hist(bins(bin_mode=mode)))

    assert found == [(("chart", "histogram", "bin_mode"), "chart-histogram-invalid")]


def test_histogram_unknown_mode_message_is_in_korean() -> None:
    assert _messages(_hist(bins(bin_mode="log"))) == ["구간 방식은 auto·count·width 중 하나입니다"]


@pytest.mark.parametrize(
    "shape",
    [
        3,
        "auto",
        [],
        True,
        {},
        {k: v for k, v in AUTO_BINS.items() if k != "underflow"},
        {**AUTO_BINS, "extra": 1},
    ],
    ids=["number", "string", "list", "bool", "empty", "missing-key", "extra-key"],
)
def test_histogram_bad_shape_is_rejected_at_histogram(shape: object) -> None:
    found = _issues(_hist(shape))

    assert found == [(LOC_HIST, "chart-histogram-invalid")]


def test_histogram_bad_shape_message_is_in_korean() -> None:
    assert _messages(_hist(3)) == ["구간 설정 형식이 올바르지 않습니다"]


# ---- 히스토그램: 오버플로·언더플로 ----


def test_histogram_overflow_must_exceed_underflow() -> None:
    equal = _issues(_hist(bins(underflow=10, overflow=10)))
    reversed_ = _issues(_hist(bins(underflow=11, overflow=10)))

    assert equal == [(("chart", "histogram", "overflow"), "chart-range-order")]
    assert reversed_ == [(("chart", "histogram", "overflow"), "chart-range-order")]


def test_histogram_overflow_order_message_is_in_korean() -> None:
    assert _messages(_hist(bins(underflow=10, overflow=10))) == [
        "오버플로 구간은 언더플로 구간보다 커야 합니다"
    ]


def test_histogram_accepts_underflow_below_overflow() -> None:
    assert _raw_of(_hist(bins(underflow=9, overflow=10))).histogram == bins(
        underflow=9, overflow=10
    )


@pytest.mark.parametrize("key", ["overflow", "underflow"])
def test_histogram_single_overflow_side_is_accepted(key: str) -> None:
    assert _raw_of(_hist(bins(**{key: 5}))).histogram[key] == 5


@pytest.mark.parametrize("key", ["overflow", "underflow"])
@pytest.mark.parametrize("number", ["5", True, float("inf"), float("nan"), SAFE + 1])
def test_histogram_overflow_sides_must_be_finite_numbers(key: str, number: object) -> None:
    found = _issues(_hist(bins(**{key: number})))

    assert [location for location, _ in found] == [("chart", "histogram", key)]


# ---- 폭포: 마지막에 합계 ----


def test_waterfall_show_total_round_trips() -> None:
    chart = raw_chart("waterfall", 0, [1], show_total=True)

    assert _raw_of(chart).show_total is True


def test_waterfall_show_total_defaults_to_false() -> None:
    assert _raw_of(raw_chart("waterfall", 0, [1])).show_total is False


@pytest.mark.parametrize("flag", ["yes", 1, 0, None])
def test_show_total_non_bool_is_flag_invalid(flag: object) -> None:
    found = _issues(raw_chart("waterfall", 0, [1], show_total=flag))

    assert found == [(("chart", "show_total"), "chart-flag-invalid")]


# ---- 다른 종류에서 옵션을 쓰면 ----


@pytest.mark.parametrize("kind", ["bar", "line_markers", "pie", "pareto", "combo"])
def test_histogram_option_on_wrong_kind_reports_option_invalid(kind: str) -> None:
    values = [1, 2] if kind == "combo" else [1]
    chart = raw_chart(kind, 0, values, histogram=bins())

    assert _issues(chart) == [(LOC_HIST, "chart-option-invalid")]


@pytest.mark.parametrize("kind", ["bar", "histogram", "pareto", "funnel", "combo"])
def test_show_total_on_wrong_kind_reports_option_invalid(kind: str) -> None:
    values = [1, 2] if kind == "combo" else [1]
    category = None if kind == "histogram" else 0
    chart = raw_chart(kind, category, values, show_total=True)

    assert _issues(chart) == [(("chart", "show_total"), "chart-option-invalid")]


@pytest.mark.parametrize("kind", ["bar", "waterfall", "histogram", "scatter"])
def test_combo_series_on_wrong_kind_reports_option_invalid(kind: str) -> None:
    values = [1, 2] if kind == "scatter" else [1]
    category = None if kind == "histogram" else 0
    chart = raw_chart(
        kind, category, values, combo_series=[combo_item(), combo_item("line")][: len(values)]
    )

    assert _issues(chart) == [(("chart", "combo_series"), "chart-option-invalid")]


def test_option_invalid_message_is_in_korean() -> None:
    assert _messages(raw_chart("bar", 0, [1], show_total=True)) == [
        "이 차트는 이 옵션을 쓰지 않습니다"
    ]


@pytest.mark.parametrize("kind", ["bar", "pie", "scatter", "pareto"])
def test_options_are_normalized_to_defaults_on_other_kinds(kind: str) -> None:
    values = [1, 2] if kind == "scatter" else [1]

    normalized = _raw_of(raw_chart(kind, 0, values))

    assert (normalized.histogram, normalized.show_total, normalized.combo_series) == (
        None,
        False,
        None,
    )


# ---- 콤보: 계열별 설정 ----


def test_combo_without_series_settings_fills_legacy_rule() -> None:
    chart = _combo(None, [1, 2, 3], secondary_axis=True)

    assert _raw_of(chart).combo_series == [
        combo_item("column"),
        combo_item("line", secondary=True),
        combo_item("line", secondary=True),
    ]


def test_combo_without_series_settings_and_secondary_off_keeps_lines_on_primary() -> None:
    assert _raw_of(_combo(None, [1, 2])).combo_series == [combo_item("column"), combo_item("line")]


@pytest.mark.parametrize(
    "kind", ["column", "stacked_column", "line", "line_markers", "area", "stacked_area"]
)
def test_combo_series_accepts_each_series_type(kind: str) -> None:
    series = [combo_item(kind), combo_item("line")]

    assert _raw_of(_combo(series)).combo_series == series


def test_combo_series_keeps_order_and_secondary_flags() -> None:
    series = [
        combo_item("stacked_area"),
        combo_item("column"),
        combo_item("line_markers", secondary=True),
    ]

    normalized = _raw_of(_combo(series, [3, 1, 2], secondary_axis=True))

    assert normalized.combo_series == series
    assert normalized.values == [3, 1, 2]


@pytest.mark.parametrize("length", [0, 1, 3])
def test_combo_series_length_must_match_values(length: int) -> None:
    series = [combo_item() for _ in range(length)]

    found = _issues(_combo(series, [1, 2]))

    assert (("chart", "combo_series"), "chart-combo-invalid") in found


def test_combo_series_length_message_is_in_korean() -> None:
    assert _messages(_combo([combo_item()], [1, 2])) == ["계열 설정 수가 값 열 수와 같아야 합니다"]


def test_combo_series_unknown_type_is_reported_at_the_item() -> None:
    found = _issues(_combo([combo_item("column"), combo_item("bar")]))

    assert found == [(("chart", "combo_series", 1), "chart-combo-invalid")]


@pytest.mark.parametrize(
    "item",
    [
        1,
        "line",
        None,
        {},
        {"type": "line"},
        {"secondary": False},
        {"type": "line", "secondary": 1},
        {"type": "line", "secondary": False, "extra": 1},
    ],
    ids=[
        "number",
        "string",
        "null",
        "empty",
        "no-secondary",
        "no-type",
        "secondary-int",
        "extra-key",
    ],
)
def test_combo_series_bad_item_shape_is_reported_at_the_item(item: object) -> None:
    found = _issues(_combo([combo_item(), item]))

    assert found == [(("chart", "combo_series", 1), "chart-combo-invalid")]


@pytest.mark.parametrize("series", ["line", 3, {"type": "line"}, True])
def test_combo_series_that_is_not_a_list_is_reported_at_the_option(series: object) -> None:
    found = _issues(_combo(series))

    assert found == [(("chart", "combo_series"), "chart-combo-invalid")]


def test_combo_all_secondary_is_rejected() -> None:
    series = [combo_item("column", secondary=True), combo_item("line", secondary=True)]

    found = _issues(_combo(series, secondary_axis=True))

    assert found == [(("chart", "combo_series"), "chart-combo-secondary-all")]


def test_combo_all_secondary_message_is_in_korean() -> None:
    series = [combo_item("column", secondary=True), combo_item("line", secondary=True)]

    assert _messages(_combo(series, secondary_axis=True)) == [
        "모든 계열을 보조 축에 둘 수 없습니다"
    ]


def test_combo_secondary_axis_mismatch_is_rejected() -> None:
    series = [combo_item("column"), combo_item("line", secondary=True)]

    found = _issues(_combo(series, secondary_axis=False))

    assert found == [(("chart", "secondary_axis"), "chart-secondary-mismatch")]


def test_combo_secondary_axis_mismatch_message_is_in_korean() -> None:
    series = [combo_item("column"), combo_item("line", secondary=True)]

    assert _messages(_combo(series)) == ["보조 축 설정이 계열 설정과 맞지 않습니다"]


def test_combo_secondary_axis_true_without_any_secondary_series_is_a_mismatch() -> None:
    found = _issues(_combo([combo_item(), combo_item("line")], secondary_axis=True))

    assert found == [(("chart", "secondary_axis"), "chart-secondary-mismatch")]


def test_combo_secondary_axis_is_normalized_from_series() -> None:
    series = [combo_item("column"), combo_item("line", secondary=True)]

    normalized = _raw_of(_combo(series, secondary_axis=True))

    assert normalized.secondary_axis is True
    assert normalized.secondary_axis == any(s["secondary"] for s in normalized.combo_series)


def test_normalized_options_parse_to_the_same_settings() -> None:
    chart = _combo(None, [1, 2, 3], secondary_axis=True)
    definition = parse_report_definition(ONE)
    settings = parse_chart(chart, definition)

    assert parse_chart(settings.to_raw(), definition) == settings


@pytest.mark.parametrize("length", [11, 500])
def test_combo_series_longer_than_the_value_limit_reports_only_the_length(length: int) -> None:
    series = [{"type": "bogus", "secondary": False} for _ in range(length)]

    found = _issues(_combo(series, [1, 2]))

    assert found == [(("chart", "combo_series"), "chart-combo-invalid")]
