"""차트 옵션 3개(histogram·show_total·combo_series)의 검증과 정규화(RC-R14~RC-R17).

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


@pytest.mark.parametrize("given", [None, AUTO_BINS])
def test_histogram_without_bins_is_normalized_to_auto(given: object) -> None:
    """구간 설정이 없거나 auto 기본값이면 자동 구간으로 정규화한다.

    테스트 코드: RC-020
    """
    # when: 구간 설정이 null 또는 auto 기본값인 히스토그램을 검증해 정규화한다
    actual = _raw_of(_hist(given)).histogram

    # then: 구간은 auto이고 나머지 칸은 null이다
    assert actual == AUTO_BINS


def test_histogram_keeps_a_valid_bin_setting() -> None:
    """올바른 구간 수 설정은 오버플로·언더플로와 함께 그대로 저장한다.

    테스트 코드: RC-021, RC-023
    """
    # given: 구간 수 8, 오버플로 100.5, 언더플로 -10 설정
    given = bins(bin_mode="count", bin_count=8, overflow=100.5, underflow=-10)

    # when: 히스토그램을 검증해 정규화한다
    actual = _raw_of(_hist(given)).histogram

    # then: 구간 설정이 입력 그대로다
    assert actual == given


def test_histogram_width_mode_keeps_width() -> None:
    """올바른 구간 너비 설정은 그대로 저장한다.

    테스트 코드: RC-021
    """
    # given: 구간 너비 2.5 설정
    given = bins(bin_mode="width", bin_width=2.5)

    # when: 히스토그램을 검증해 정규화한다
    actual = _raw_of(_hist(given)).histogram

    # then: 구간 설정이 입력 그대로다
    assert actual == given


@pytest.mark.parametrize("count", [1, 100])
def test_histogram_count_mode_accepts_1_and_100(count: int) -> None:
    """구간 수는 1과 100을 받는다.

    테스트 코드: RC-021
    """
    # given: 구간 수 방식의 경계 설정(1, 100)
    given = bins(bin_mode="count", bin_count=count)

    # when: 히스토그램을 검증해 정규화한다
    actual = _raw_of(_hist(given)).histogram["bin_count"]

    # then: 구간 수가 그대로다
    assert actual == count


@pytest.mark.parametrize("count", [0, 101, -1, 2.5, "3", True, None])
def test_histogram_count_mode_rejects_out_of_range_and_non_integers(count: object) -> None:
    """구간 수가 범위 밖이거나 정수가 아니면 `histogram.bin_count` 위반이다.

    테스트 코드: RC-021
    """
    # when: 0·101·음수·소수·문자열·bool·null 구간 수로 검증한다
    found = _issues(_hist(bins(bin_mode="count", bin_count=count)))

    # then: `["chart","histogram","bin_count"]` chart-histogram-invalid 하나뿐이다
    assert found == [(("chart", "histogram", "bin_count"), "chart-histogram-invalid")]


def test_histogram_count_message_is_in_korean() -> None:
    """구간 수 위반 문구는 한국어다.

    테스트 코드: RC-021
    """
    # when: 구간 수 0으로 검증해 문구를 모은다
    messages = _messages(_hist(bins(bin_mode="count", bin_count=0)))

    # then: "구간 수는 1~100의 정수입니다"다
    assert messages == ["구간 수는 1~100의 정수입니다"]


@pytest.mark.parametrize("width", [0.5, 1, SAFE])
def test_histogram_width_mode_accepts_positive_finite_widths(width: float) -> None:
    """구간 너비는 0보다 큰 유한 숫자(최대 2^53-1)를 받는다.

    테스트 코드: RC-021
    """
    # given: 구간 너비 방식 설정
    given = bins(bin_mode="width", bin_width=width)

    # when: 히스토그램을 검증해 정규화한다
    actual = _raw_of(_hist(given)).histogram["bin_width"]

    # then: 구간 너비가 그대로다
    assert actual == width


@pytest.mark.parametrize(
    "width", [0, 0.0, -1, float("inf"), float("-inf"), float("nan"), SAFE + 1, True, "1", None]
)
def test_histogram_width_mode_rejects_zero_negative_and_non_finite(width: object) -> None:
    """구간 너비가 0 이하·무한·NaN·한도 초과·숫자가 아니면 `histogram.bin_width` 위반이다.

    테스트 코드: RC-021
    """
    # when: 0·음수·무한·NaN·한도 초과·bool·문자열·null 구간 너비로 검증한다
    found = _issues(_hist(bins(bin_mode="width", bin_width=width)))

    # then: `["chart","histogram","bin_width"]` chart-histogram-invalid 하나뿐이다
    assert found == [(("chart", "histogram", "bin_width"), "chart-histogram-invalid")]


def test_histogram_width_message_is_in_korean() -> None:
    """구간 너비 위반 문구는 한국어다.

    테스트 코드: RC-021
    """
    # when: 구간 너비 0으로 검증해 문구를 모은다
    messages = _messages(_hist(bins(bin_mode="width", bin_width=0)))

    # then: "구간 너비는 0보다 큰 숫자입니다"다
    assert messages == ["구간 너비는 0보다 큰 숫자입니다"]


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
    """구간 방식이 쓰지 않는 칸에 값이 있으면 그 칸의 위반이다.

    테스트 코드: RC-021
    """
    # when: 방식이 쓰지 않는 구간 수·너비에 값을 준 히스토그램을 검증한다
    found = _issues(_hist(given))

    # then: 그 칸 위치의 chart-histogram-invalid 하나뿐이다
    assert found == [(("chart", "histogram", key), "chart-histogram-invalid")]


def test_histogram_unused_field_message_is_in_korean() -> None:
    """쓰지 않는 칸 위반 문구는 한국어다.

    테스트 코드: RC-021
    """
    # when: auto 방식에 구간 수를 준 히스토그램을 검증해 문구를 모은다
    actual = _messages(_hist(bins(bin_mode="auto", bin_count=5)))

    # then: "이 구간 방식에서는 비워 두세요"다
    assert actual == ["이 구간 방식에서는 비워 두세요"]


@pytest.mark.parametrize("mode", ["log", "AUTO", "", None, 1, True])
def test_histogram_unknown_mode_is_rejected_at_bin_mode(mode: object) -> None:
    """모르는 구간 방식은 `histogram.bin_mode` 위반이다.

    테스트 코드: RC-022
    """
    # when: log·대문자·빈 글자·null·숫자·bool 구간 방식으로 검증한다
    found = _issues(_hist(bins(bin_mode=mode)))

    # then: `["chart","histogram","bin_mode"]` chart-histogram-invalid 하나뿐이다
    assert found == [(("chart", "histogram", "bin_mode"), "chart-histogram-invalid")]


def test_histogram_unknown_mode_message_is_in_korean() -> None:
    """구간 방식 위반 문구는 한국어다.

    테스트 코드: RC-022
    """
    # when: 구간 방식 log로 검증해 문구를 모은다
    actual = _messages(_hist(bins(bin_mode="log")))

    # then: "구간 방식은 auto·count·width 중 하나입니다"다
    assert actual == ["구간 방식은 auto·count·width 중 하나입니다"]


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
    """구간 설정이 5키 객체가 아니면 `histogram` 위반이다.

    테스트 코드: RC-022
    """
    # when: 숫자·문자열·목록·bool·빈 객체·키 누락·키 추가 설정으로 검증한다
    found = _issues(_hist(shape))

    # then: `["chart","histogram"]` chart-histogram-invalid 하나뿐이다
    assert found == [(LOC_HIST, "chart-histogram-invalid")]


def test_histogram_bad_shape_message_is_in_korean() -> None:
    """구간 설정 모양 위반 문구는 한국어다.

    테스트 코드: RC-022
    """
    # when: 숫자 3을 구간 설정으로 주고 검증해 문구를 모은다
    actual = _messages(_hist(3))

    # then: "구간 설정 형식이 올바르지 않습니다"다
    assert actual == ["구간 설정 형식이 올바르지 않습니다"]


def test_histogram_overflow_must_exceed_underflow() -> None:
    """오버플로는 언더플로보다 커야 하고 같거나 작으면 chart-range-order다.

    테스트 코드: RC-023
    """
    # when: 언더플로와 오버플로가 같은 설정과 거꾸로 된 설정을 각각 검증한다
    equal = _issues(_hist(bins(underflow=10, overflow=10)))
    reversed_ = _issues(_hist(bins(underflow=11, overflow=10)))

    # then: 둘 다 `histogram.overflow`의 chart-range-order 하나뿐이다
    assert equal == [(("chart", "histogram", "overflow"), "chart-range-order")]
    assert reversed_ == [(("chart", "histogram", "overflow"), "chart-range-order")]


def test_histogram_overflow_order_message_is_in_korean() -> None:
    """오버플로 순서 위반 문구는 한국어다.

    테스트 코드: RC-023
    """
    # when: 언더플로와 오버플로가 같은 설정을 검증해 문구를 모은다
    actual = _messages(_hist(bins(underflow=10, overflow=10)))

    # then: "오버플로 구간은 언더플로 구간보다 커야 합니다"다
    assert actual == ["오버플로 구간은 언더플로 구간보다 커야 합니다"]


def test_histogram_accepts_underflow_below_overflow() -> None:
    """언더플로가 오버플로보다 작으면 받는다.

    테스트 코드: RC-023
    """
    # when: 언더플로 9, 오버플로 10 설정을 검증해 정규화한다
    actual = _raw_of(_hist(bins(underflow=9, overflow=10))).histogram

    # then: 구간 설정이 입력 그대로다
    assert actual == bins(underflow=9, overflow=10)


@pytest.mark.parametrize("key", ["overflow", "underflow"])
def test_histogram_single_overflow_side_is_accepted(key: str) -> None:
    """오버플로나 언더플로 한쪽만 줘도 받는다.

    테스트 코드: RC-023
    """
    # when: 한쪽만 5를 준 설정을 검증해 정규화한다
    actual = _raw_of(_hist(bins(**{key: 5}))).histogram[key]

    # then: 그 칸이 5로 보관된다
    assert actual == 5


@pytest.mark.parametrize("key", ["overflow", "underflow"])
@pytest.mark.parametrize("number", ["5", True, float("inf"), float("nan"), SAFE + 1])
def test_histogram_overflow_sides_must_be_finite_numbers(key: str, number: object) -> None:
    """오버플로·언더플로가 유한 숫자가 아니면 그 칸의 위반이다.

    테스트 코드: RC-023
    """
    # when: 문자열·bool·무한·NaN·한도 초과 값으로 검증한다
    found = _issues(_hist(bins(**{key: number})))

    # then: 위반 위치가 그 칸 하나뿐이다
    assert [location for location, _ in found] == [("chart", "histogram", key)]


def test_waterfall_show_total_round_trips() -> None:
    """폭포의 합계 막대 켜기는 그대로 저장한다.

    테스트 코드: RC-024
    """
    # given: 합계 막대를 켠 폭포 차트
    chart = raw_chart("waterfall", 0, [1], show_total=True)

    # when: 검증해 정규화한다
    actual = _raw_of(chart).show_total

    # then: show_total이 true다
    assert actual is True


def test_waterfall_show_total_defaults_to_false() -> None:
    """폭포의 합계 막대는 기본이 꺼짐이다.

    테스트 코드: RC-024
    """
    # when: show_total을 생략한 폭포를 검증해 정규화한다
    actual = _raw_of(raw_chart("waterfall", 0, [1])).show_total

    # then: show_total이 false다
    assert actual is False


@pytest.mark.parametrize("flag", ["yes", 1, 0, None])
def test_show_total_non_bool_is_flag_invalid(flag: object) -> None:
    """합계 막대 값이 bool이 아니면 chart-flag-invalid다.

    테스트 코드: RC-024
    """
    # when: 문자열·숫자·null show_total로 폭포를 검증한다
    found = _issues(raw_chart("waterfall", 0, [1], show_total=flag))

    # then: `["chart","show_total"]` chart-flag-invalid 하나뿐이다
    assert found == [(("chart", "show_total"), "chart-flag-invalid")]


@pytest.mark.parametrize("kind", ["bar", "line_markers", "pie", "pareto", "combo"])
def test_histogram_option_on_wrong_kind_reports_option_invalid(kind: str) -> None:
    """히스토그램이 아닌 종류에 구간 설정을 주면 chart-option-invalid다.

    테스트 코드: RC-025
    """
    values = [1, 2] if kind == "combo" else [1]
    # given: 구간 설정을 단 차트
    chart = raw_chart(kind, 0, values, histogram=bins())

    # when: 히스토그램이 아닌 종류로 검증한다
    actual = _issues(chart)

    # then: `["chart","histogram"]` chart-option-invalid 하나뿐이다
    assert actual == [(LOC_HIST, "chart-option-invalid")]


@pytest.mark.parametrize("kind", ["bar", "histogram", "pareto", "funnel", "combo"])
def test_show_total_on_wrong_kind_reports_option_invalid(kind: str) -> None:
    """폭포가 아닌 종류에 합계 막대를 켜면 chart-option-invalid다.

    테스트 코드: RC-024, RC-025
    """
    values = [1, 2] if kind == "combo" else [1]
    category = None if kind == "histogram" else 0
    # given: 합계 막대를 켠 차트
    chart = raw_chart(kind, category, values, show_total=True)

    # when: 폭포가 아닌 종류로 검증한다
    actual = _issues(chart)

    # then: `["chart","show_total"]` chart-option-invalid 하나뿐이다
    assert actual == [(("chart", "show_total"), "chart-option-invalid")]


@pytest.mark.parametrize("kind", ["bar", "waterfall", "histogram", "scatter"])
def test_combo_series_on_wrong_kind_reports_option_invalid(kind: str) -> None:
    """콤보가 아닌 종류에 계열 설정을 주면 chart-option-invalid다.

    테스트 코드: RC-025
    """
    values = [1, 2] if kind == "scatter" else [1]
    category = None if kind == "histogram" else 0
    # given: 계열 설정을 단 차트
    chart = raw_chart(
        kind, category, values, combo_series=[combo_item(), combo_item("line")][: len(values)]
    )

    # when: 콤보가 아닌 종류로 검증한다
    actual = _issues(chart)

    # then: `["chart","combo_series"]` chart-option-invalid 하나뿐이다
    assert actual == [(("chart", "combo_series"), "chart-option-invalid")]


def test_option_invalid_message_is_in_korean() -> None:
    """옵션 위반 문구는 한국어다.

    테스트 코드: RC-025
    """
    # when: 막대에 합계 막대를 켜고 검증해 문구를 모은다
    actual = _messages(raw_chart("bar", 0, [1], show_total=True))

    # then: "이 차트는 이 옵션을 쓰지 않습니다"다
    assert actual == ["이 차트는 이 옵션을 쓰지 않습니다"]


@pytest.mark.parametrize("kind", ["bar", "pie", "scatter", "pareto"])
def test_options_are_normalized_to_defaults_on_other_kinds(kind: str) -> None:
    """옵션을 쓰지 않는 종류의 옵션은 기본값으로 정규화한다.

    테스트 코드: RC-025
    """
    # when: 옵션 없는 차트를 검증해 정규화한다
    values = [1, 2] if kind == "scatter" else [1]

    normalized = _raw_of(raw_chart(kind, 0, values))

    # then: 구간 null, 합계 false, 계열 설정 null이다
    assert (normalized.histogram, normalized.show_total, normalized.combo_series) == (
        None,
        False,
        None,
    )


def test_combo_without_series_settings_fills_legacy_rule() -> None:
    """계열 설정이 없는 콤보는 첫 값 막대·나머지 꺾은선으로 채운다.

    테스트 코드: RC-026
    """
    # given: 계열 설정 없이 보조 축을 켠 값 3개 콤보
    chart = _combo(None, [1, 2, 3], secondary_axis=True)

    # when: 검증해 정규화한다
    actual = _raw_of(chart).combo_series

    # then: 첫 값은 묶은 세로 막대, 나머지는 보조 축 꺾은선이다
    assert actual == [
        combo_item("column"),
        combo_item("line", secondary=True),
        combo_item("line", secondary=True),
    ]


def test_combo_without_series_settings_and_secondary_off_keeps_lines_on_primary() -> None:
    """보조 축을 끄면 채워진 꺾은선은 기본 축에 둔다.

    테스트 코드: RC-026
    """
    # when: 계열 설정과 보조 축 없이 콤보를 검증해 정규화한다
    actual = _raw_of(_combo(None, [1, 2])).combo_series

    # then: 막대와 기본 축 꺾은선이다
    assert actual == [combo_item("column"), combo_item("line")]


@pytest.mark.parametrize(
    "kind", ["column", "stacked_column", "line", "line_markers", "area", "stacked_area"]
)
def test_combo_series_accepts_each_series_type(kind: str) -> None:
    """계열 종류 6가지를 모두 받는다.

    테스트 코드: RC-027
    """
    # given: 첫 계열이 해당 종류인 계열 설정
    series = [combo_item(kind), combo_item("line")]

    # when: 콤보를 검증해 정규화한다
    actual = _raw_of(_combo(series)).combo_series

    # then: 계열 설정이 입력 그대로다
    assert actual == series


def test_combo_series_keeps_order_and_secondary_flags() -> None:
    """계열 설정은 순서와 보조 축 값을 그대로 보관한다.

    테스트 코드: RC-027
    """
    # given: 값 순서 [3, 1, 2]에 맞춘 계열 설정
    series = [
        combo_item("stacked_area"),
        combo_item("column"),
        combo_item("line_markers", secondary=True),
    ]

    # when: 콤보를 검증해 정규화한다
    normalized = _raw_of(_combo(series, [3, 1, 2], secondary_axis=True))

    # then: 계열 설정과 값 순서가 입력 그대로다
    assert normalized.combo_series == series
    assert normalized.values == [3, 1, 2]


@pytest.mark.parametrize("length", [0, 1, 3])
def test_combo_series_length_must_match_values(length: int) -> None:
    """계열 설정 수가 값 개수와 다르면 chart-combo-invalid다.

    테스트 코드: RC-027
    """
    # given: 값 2개에 길이 0·1·3인 계열 설정
    series = [combo_item() for _ in range(length)]

    # when: 콤보를 검증한다
    found = _issues(_combo(series, [1, 2]))

    # then: `["chart","combo_series"]` chart-combo-invalid 위반이 있다
    assert (("chart", "combo_series"), "chart-combo-invalid") in found


def test_combo_series_length_message_is_in_korean() -> None:
    """계열 설정 수 위반 문구는 한국어다.

    테스트 코드: RC-027
    """
    # when: 값 2개에 계열 설정 1개로 검증해 문구를 모은다
    actual = _messages(_combo([combo_item()], [1, 2]))

    # then: "계열 설정 수가 값 열 수와 같아야 합니다"다
    assert actual == ["계열 설정 수가 값 열 수와 같아야 합니다"]


def test_combo_series_unknown_type_is_reported_at_the_item() -> None:
    """모르는 계열 종류는 그 항목 위치의 위반이다.

    테스트 코드: RC-027
    """
    # when: 둘째 계열 종류가 bar인 콤보를 검증한다
    found = _issues(_combo([combo_item("column"), combo_item("bar")]))

    # then: `["chart","combo_series",1]` chart-combo-invalid 하나뿐이다
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
    """계열 항목이 {type, secondary} 정확히 2키가 아니면 그 항목 위치의 위반이다.

    테스트 코드: RC-027
    """
    # when: 숫자·문자열·null·키 누락·secondary가 정수·키 추가 항목으로 검증한다
    found = _issues(_combo([combo_item(), item]))

    # then: `["chart","combo_series",1]` chart-combo-invalid 하나뿐이다
    assert found == [(("chart", "combo_series", 1), "chart-combo-invalid")]


@pytest.mark.parametrize("series", ["line", 3, {"type": "line"}, True])
def test_combo_series_that_is_not_a_list_is_reported_at_the_option(series: object) -> None:
    """계열 설정이 목록이 아니면 옵션 위치의 위반이다.

    테스트 코드: RC-027
    """
    # when: 문자열·숫자·객체·bool 계열 설정으로 검증한다
    found = _issues(_combo(series))

    # then: `["chart","combo_series"]` chart-combo-invalid 하나뿐이다
    assert found == [(("chart", "combo_series"), "chart-combo-invalid")]


def test_combo_all_secondary_is_rejected() -> None:
    """모든 계열을 보조 축에 두면 chart-combo-secondary-all이다.

    테스트 코드: RC-028
    """
    # given: 모든 계열이 보조 축인 계열 설정
    series = [combo_item("column", secondary=True), combo_item("line", secondary=True)]

    # when: 콤보를 검증한다
    found = _issues(_combo(series, secondary_axis=True))

    # then: `["chart","combo_series"]` chart-combo-secondary-all 하나뿐이다
    assert found == [(("chart", "combo_series"), "chart-combo-secondary-all")]


def test_combo_all_secondary_message_is_in_korean() -> None:
    """전부 보조 축 위반 문구는 한국어다.

    테스트 코드: RC-028
    """
    # given: 모든 계열이 보조 축인 계열 설정
    series = [combo_item("column", secondary=True), combo_item("line", secondary=True)]

    # when: 콤보를 검증해 문구를 모은다
    actual = _messages(_combo(series, secondary_axis=True))

    # then: "모든 계열을 보조 축에 둘 수 없습니다"다
    assert actual == ["모든 계열을 보조 축에 둘 수 없습니다"]


def test_combo_secondary_axis_mismatch_is_rejected() -> None:
    """secondary_axis가 계열 설정과 다르면 chart-secondary-mismatch다.

    테스트 코드: RC-028
    """
    # given: 보조 축 계열이 있는데 secondary_axis를 끈 콤보
    series = [combo_item("column"), combo_item("line", secondary=True)]

    # when: 검증한다
    found = _issues(_combo(series, secondary_axis=False))

    # then: `["chart","secondary_axis"]` chart-secondary-mismatch 하나뿐이다
    assert found == [(("chart", "secondary_axis"), "chart-secondary-mismatch")]


def test_combo_secondary_axis_mismatch_message_is_in_korean() -> None:
    """보조 축 불일치 문구는 한국어다.

    테스트 코드: RC-028
    """
    # given: 보조 축 계열이 있는데 secondary_axis를 생략한 콤보
    series = [combo_item("column"), combo_item("line", secondary=True)]

    # when: 검증해 문구를 모은다
    actual = _messages(_combo(series))

    # then: "보조 축 설정이 계열 설정과 맞지 않습니다"다
    assert actual == ["보조 축 설정이 계열 설정과 맞지 않습니다"]


def test_combo_secondary_axis_true_without_any_secondary_series_is_a_mismatch() -> None:
    """secondary_axis만 켜고 보조 축 계열이 없어도 불일치다.

    테스트 코드: RC-028
    """
    # when: 보조 축 계열 없이 secondary_axis를 켠 콤보를 검증한다
    found = _issues(_combo([combo_item(), combo_item("line")], secondary_axis=True))

    # then: `["chart","secondary_axis"]` chart-secondary-mismatch 하나뿐이다
    assert found == [(("chart", "secondary_axis"), "chart-secondary-mismatch")]


def test_combo_secondary_axis_is_normalized_from_series() -> None:
    """정규화한 secondary_axis는 계열 설정에서 계산한 값이다.

    테스트 코드: RC-028
    """
    # given: 보조 축 계열이 하나 있는 콤보
    series = [combo_item("column"), combo_item("line", secondary=True)]

    # when: 검증해 정규화한다
    normalized = _raw_of(_combo(series, secondary_axis=True))

    # then: secondary_axis가 켜져 있고 계열의 보조 축 여부와 같다
    assert normalized.secondary_axis is True
    assert normalized.secondary_axis == any(s["secondary"] for s in normalized.combo_series)


def test_normalized_options_parse_to_the_same_settings() -> None:
    """정규화한 옵션을 다시 검증하면 같은 설정이다.

    테스트 코드: RC-029
    """
    # given: 계열 설정 없이 보조 축을 켠 값 3개 콤보와 그 검증 결과
    chart = _combo(None, [1, 2, 3], secondary_axis=True)
    definition = parse_report_definition(ONE)
    settings = parse_chart(chart, definition)

    # when: 정규화한 원시 차트를 다시 검증한다
    actual = parse_chart(settings.to_raw(), definition)

    # then: 처음 설정과 같다
    assert actual == settings


@pytest.mark.parametrize("length", [11, 500])
def test_combo_series_longer_than_the_value_limit_reports_only_the_length(length: int) -> None:
    """계열 설정이 값 한도보다 길면 항목별 위반 없이 길이 위반 하나뿐이다.

    테스트 코드: RC-027
    """
    # given: 잘못된 종류의 계열 항목 11~500개
    series = [{"type": "bogus", "secondary": False} for _ in range(length)]

    # when: 값 2개 콤보를 검증한다
    found = _issues(_combo(series, [1, 2]))

    # then: `["chart","combo_series"]` chart-combo-invalid 하나뿐이다
    assert found == [(("chart", "combo_series"), "chart-combo-invalid")]
