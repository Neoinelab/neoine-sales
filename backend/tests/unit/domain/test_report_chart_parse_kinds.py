"""새 차트 종류 23종의 검증 `parse_chart`: 규칙표(RC-R2)대로 받아들이고 어긋나면 거절한다.

기존 10종은 `test_report_chart_parse.py`가 고정한다.
위치는 `("chart", ...)`이고 컬럼은 정의 `columns`의 index로 가리킨다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.report.chart_kinds import ChartKind
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.parse import parse_report_definition
from app.domain.report.parse_chart import parse_chart
from tests.support.chart_defs import chart_definition, chart_issues, raw_chart

if TYPE_CHECKING:
    from app.domain.report.chart import ChartSettings
    from app.domain.report.raw import RawReportDefinition

ONE = chart_definition(1, 11)  # 0 = 그룹, 1..11 = 집계 값
TWO = chart_definition(2, 11)  # 0·1 = 그룹, 2..12 = 집계 값
UNGROUPED = chart_definition(0)  # 0 = deal.code(텍스트), 1 = deal.amount(숫자, 집계 없음)

NEW_KINDS = [
    "stacked_horizontal_bar",
    "stacked_100_horizontal_bar",
    "line_markers",
    "stacked_line",
    "stacked_line_markers",
    "stacked_100_line",
    "stacked_100_line_markers",
    "stacked_area",
    "stacked_100_area",
    "scatter_smooth_markers",
    "scatter_smooth",
    "scatter_line_markers",
    "scatter_line",
    "bubble",
    "radar",
    "radar_markers",
    "radar_filled",
    "treemap",
    "sunburst",
    "histogram",
    "pareto",
    "waterfall",
    "funnel",
]
SCATTERS = [
    "scatter",
    "scatter_smooth_markers",
    "scatter_smooth",
    "scatter_line_markers",
    "scatter_line",
]
CARTESIAN = [
    "stacked_horizontal_bar",
    "stacked_100_horizontal_bar",
    "line_markers",
    "stacked_line",
    "stacked_line_markers",
    "stacked_100_line",
    "stacked_100_line_markers",
    "stacked_area",
    "stacked_100_area",
    "radar",
    "radar_markers",
    "radar_filled",
]
PERCENT = [
    "stacked_100_bar",
    "stacked_100_horizontal_bar",
    "stacked_100_line",
    "stacked_100_line_markers",
    "stacked_100_area",
]
ONE_GROUP_ONLY = [
    "pie",
    "doughnut",
    "scatter",
    "scatter_smooth_markers",
    "scatter_smooth",
    "scatter_line_markers",
    "scatter_line",
    "bubble",
    "pareto",
    "waterfall",
    "funnel",
    "combo",
]


def _parse(definition: RawReportDefinition, chart: Any) -> ChartSettings:  # noqa: ANN401
    return parse_chart(chart, parse_report_definition(definition))


def _values_for(kind: str) -> list[int]:
    if kind == "bubble":
        return [1, 2, 3]
    if kind.startswith("scatter") or kind == "combo":
        return [1, 2]
    return [1]


def _minimal(kind: str) -> Any:  # noqa: ANN401 - RawChart
    """ONE 기준 최소 설정. 히스토그램은 범주를 쓰지 않는다."""
    return raw_chart(kind, None if kind == "histogram" else 0, _values_for(kind))


def _issue(definition: RawReportDefinition, chart: Any) -> list[tuple[Any, str]]:  # noqa: ANN401
    return chart_issues(definition, chart)


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_each_new_kind_with_valid_columns_parses(kind: str) -> None:
    """규칙에 맞는 최소 설정이면 새 23종을 모두 받아들인다."""
    # when: 종류별 최소 설정을 검증한다 (전제: 그룹 1개 정의, 히스토그램은 범주 없음)
    settings = _parse(ONE, _minimal(kind))

    # then: 종류와 범주가 그대로이고 계열은 없다
    assert settings.kind == ChartKind(kind)
    assert settings.category == (None if kind == "histogram" else 0)
    assert settings.series is None


@pytest.mark.parametrize(
    "kind", ["stacked_horizontal_bar", "stacked_line", "radar", "stacked_area"]
)
def test_cartesian_like_new_kinds_accept_two_groups_with_a_series(kind: str) -> None:
    """새 막대·꺾은선·영역·방사형은 그룹 2개와 계열, 행/열 전환을 받아들인다.

    테스트 코드: RC-009
    """
    # when: 계열과 swap을 지정해 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    settings = _parse(TWO, raw_chart(kind, 0, [2], series=1, swap=True))

    # then: 범주·계열·값·swap이 그대로다
    assert (settings.category, settings.series, settings.values, settings.swap) == (
        0,
        1,
        (2,),
        True,
    )


@pytest.mark.parametrize("kind", ONE_GROUP_ONLY)
def test_kind_with_too_many_groups_reports_chart_kind_groups(kind: str) -> None:
    """그룹이 2개면 그룹 하나만 허용하는 종류는 chart-kind-groups다.

    테스트 코드: RC-006
    """
    # given: 종류에 맞는 값 목록(그룹 2개 정의의 값 컬럼은 2번부터)
    chart = raw_chart(kind, 0, [v + 1 for v in _values_for(kind)])  # TWO의 값 컬럼은 2부터

    # when: 그룹 컬럼이 2개인 정의에서 검증한다
    found = _issue(TWO, chart)

    # then: `["chart","kind"]` chart-kind-groups 위반이 있다
    assert (("chart", "kind"), "chart-kind-groups") in found


def test_chart_kind_groups_message_is_common_to_every_kind() -> None:
    """chart-kind-groups 문구는 종류 최대 그룹 수를 넣은 공통 문구다.

    테스트 코드: RC-006
    """
    # when·then: 그룹 2개 정의에서 파레토를 검증하면 위반 문구가 "이 차트는 그룹핑 컬럼이 1개 이하일
    #   때 만들 수 있습니다"다
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(TWO, raw_chart("pareto", 0, [2]))

    (issue,) = [i for i in caught.value.issues if i.code == "chart-kind-groups"]
    assert issue.message == "이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다"


@pytest.mark.parametrize("kind", ["bar", "line_markers", "stacked_area", "radar", "treemap"])
def test_ungrouped_non_histogram_reports_needs_grouping(kind: str) -> None:
    """그룹핑 없는 정의에 히스토그램이 아닌 종류는 chart-needs-grouping 하나뿐이다.

    테스트 코드: RC-003
    """
    # when: 히스토그램이 아닌 종류로 검증한다 (전제: 그룹핑 없는 정의)
    found = _issue(UNGROUPED, raw_chart(kind, 0, [1]))

    # then: `["chart"]` chart-needs-grouping 하나뿐이다
    assert found == [(("chart",), "chart-needs-grouping")]


def test_three_groups_stay_too_many_for_the_histogram() -> None:
    """그룹이 3개면 히스토그램도 chart-too-many-groups 하나뿐이다.

    테스트 코드: RC-004
    """
    # when: 히스토그램을 검증한다 (전제: 그룹 컬럼이 3개인 정의)
    found = _issue(chart_definition(3, 2), raw_chart("histogram", None, [3]))

    # then: `["chart"]` chart-too-many-groups 하나뿐이다
    assert found == [(("chart",), "chart-too-many-groups")]


def test_ungrouped_histogram_accepts_a_number_column() -> None:
    """그룹핑 없는 정의의 히스토그램은 숫자 컬럼 하나를 받고 자동 구간으로 정규화된다.

    테스트 코드: RC-014, RC-020
    """
    # when: 숫자 컬럼을 값으로 준 히스토그램을 검증한다 (전제: 그룹핑 없는 정의)
    settings = _parse(UNGROUPED, raw_chart("histogram", None, [1]))

    # then: 범주·계열이 없고 구간은 auto 5키로 정규화된다
    assert settings.kind == ChartKind.HISTOGRAM
    assert (settings.category, settings.series, settings.values) == (None, None, (1,))
    assert settings.to_raw().histogram == {
        "bin_mode": "auto",
        "bin_count": None,
        "bin_width": None,
        "overflow": None,
        "underflow": None,
    }


def test_ungrouped_histogram_rejects_a_text_column() -> None:
    """그룹핑 없는 히스토그램의 값이 텍스트 컬럼이면 chart-value-invalid다.

    테스트 코드: RC-014
    """
    # when: 텍스트 컬럼을 값으로 준 히스토그램을 검증한다 (전제: 그룹핑 없는 정의)
    found = _issue(UNGROUPED, raw_chart("histogram", None, [0]))

    # then: `["chart","values",0]` chart-value-invalid 하나뿐이다
    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_ungrouped_histogram_rejects_a_missing_column() -> None:
    """그룹핑 없는 히스토그램의 값이 없는 컬럼이면 chart-value-invalid다.

    테스트 코드: RC-014
    """
    # when: 범위 밖 index를 값으로 준 히스토그램을 검증한다 (전제: 그룹핑 없는 정의)
    found = _issue(UNGROUPED, raw_chart("histogram", None, [99]))

    # then: `["chart","values",0]` chart-value-invalid 하나뿐이다
    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_ungrouped_histogram_needs_exactly_one_value() -> None:
    """히스토그램은 값을 정확히 1개 받는다.

    테스트 코드: RC-012
    """
    # when: 값 2개를 준 히스토그램을 검증한다 (전제: 그룹핑 없는 정의)
    found = _issue(UNGROUPED, raw_chart("histogram", None, [1, 1]))

    # then: chart-values-count 위반이 있다
    assert (("chart", "values"), "chart-values-count") in found


def test_grouped_histogram_accepts_an_aggregate_column() -> None:
    """그룹 있는 히스토그램은 집계 컬럼을 값으로 받는다.

    테스트 코드: RC-014
    """
    # when: 집계 컬럼을 값으로 준 히스토그램을 검증한다 (전제: 그룹 1개 정의)
    settings = _parse(ONE, raw_chart("histogram", None, [2]))

    # then: 범주는 null이고 값이 그대로다
    assert (settings.category, settings.values) == (None, (2,))


def test_grouped_histogram_rejects_a_group_column_as_the_value() -> None:
    """그룹 있는 히스토그램의 값이 그룹 컬럼이면 chart-value-invalid다.

    테스트 코드: RC-014
    """
    # when: 그룹 컬럼을 값으로 준 히스토그램을 검증한다
    found = _issue(ONE, raw_chart("histogram", None, [0]))

    # then: `["chart","values",0]` chart-value-invalid 하나뿐이다
    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_histogram_with_category_reports_category_invalid() -> None:
    """히스토그램에 범주를 주면 "이 차트는 범주 열을 쓰지 않습니다" 위반이다.

    테스트 코드: RC-008
    """
    # when: 범주 0을 준 히스토그램을 검증한다
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart("histogram", 0, [1]))

    # then: `["chart","category"]` chart-category-invalid 하나이고 문구는 "이 차트는 범주 열을 쓰지
    #   않습니다"다
    (issue,) = caught.value.issues
    assert issue.location == ("chart", "category")
    assert issue.code == "chart-category-invalid"
    assert issue.message == "이 차트는 범주 열을 쓰지 않습니다"


def test_non_histogram_with_null_category_reports_category_invalid() -> None:
    """히스토그램이 아닌 종류의 null 범주는 chart-category-invalid다.

    테스트 코드: RC-008
    """
    # when: 범주 null인 파레토를 검증한다
    found = _issue(ONE, raw_chart("pareto", None, [1]))

    # then: `["chart","category"]` chart-category-invalid 하나뿐이다
    assert found == [(("chart", "category"), "chart-category-invalid")]


@pytest.mark.parametrize("kind", SCATTERS)
@pytest.mark.parametrize("count", [2, 10])
def test_scatter_family_accepts_two_to_ten_values(kind: str, count: int) -> None:
    """분산형 5종은 값 2~10개를 받는다.

    테스트 코드: RC-012
    """
    # when: 값 2개와 10개로 검증한다
    settings = _parse(ONE, raw_chart(kind, 0, list(range(1, count + 1))))

    # then: 값 개수가 그대로다
    assert len(settings.values) == count


@pytest.mark.parametrize("kind", SCATTERS)
def test_scatter_with_one_value_reports_count(kind: str) -> None:
    """분산형에 값이 1개면 "2~10개" 개수 위반이다.

    테스트 코드: RC-012
    """
    # when: 값 1개로 분산형을 검증한다
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart(kind, 0, [1]))

    # then: `["chart","values"]` chart-values-count 하나이고 문구에 "2~10개"가 있다
    (issue,) = caught.value.issues
    assert (issue.location, issue.code) == (("chart", "values"), "chart-values-count")
    assert "2~10개" in issue.message


@pytest.mark.parametrize("kind", SCATTERS)
def test_scatter_with_eleven_values_reports_count(kind: str) -> None:
    """분산형에 값이 11개면 개수 위반 하나뿐이다.

    테스트 코드: RC-012
    """
    # when: 값 11개로 분산형을 검증한다
    found = _issue(ONE, raw_chart(kind, 0, list(range(1, 12))))

    # then: `["chart","values"]` chart-values-count 하나뿐이다
    assert found == [(("chart", "values"), "chart-values-count")]


@pytest.mark.parametrize("values", [[1, 2], [1, 2, 3, 4]])
def test_bubble_rejects_anything_but_three_values(values: list[int]) -> None:
    """거품형은 값이 정확히 3개가 아니면 "3개" 개수 위반이다.

    테스트 코드: RC-012
    """
    # when: 값 2개 또는 4개로 거품형을 검증한다
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart("bubble", 0, values))

    # then: `["chart","values"]` chart-values-count 하나이고 문구에 "3개"가 있다
    (issue,) = caught.value.issues
    assert (issue.location, issue.code) == (("chart", "values"), "chart-values-count")
    assert "3개" in issue.message


def test_bubble_accepts_exactly_three_values() -> None:
    """거품형은 값 3개를 받는다.

    테스트 코드: RC-012
    """
    # when: 값 3개로 거품형을 검증한다
    settings = _parse(ONE, raw_chart("bubble", 0, [1, 2, 3]))

    # then: 값이 그대로다
    assert settings.values == (1, 2, 3)


@pytest.mark.parametrize(
    "kind", ["pareto", "waterfall", "funnel", "treemap", "sunburst", "histogram"]
)
def test_single_value_kinds_reject_two_values(kind: str) -> None:
    """값 1개만 받는 종류에 2개를 주면 개수 위반 하나뿐이다.

    테스트 코드: RC-012
    """
    # given: 종류에 맞는 범주(히스토그램은 null)
    category = None if kind == "histogram" else 0

    # when: 값 2개로 검증한다
    found = _issue(ONE, raw_chart(kind, category, [1, 2]))

    # then: `["chart","values"]` chart-values-count 하나뿐이다
    assert found == [(("chart", "values"), "chart-values-count")]


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_with_two_groups_requires_a_series(kind: str) -> None:
    """트리맵·선버스트는 그룹이 2개면 계열이 필수다.

    테스트 코드: RC-009
    """
    # when: 계열 없이 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    found = _issue(TWO, raw_chart(kind, 0, [2]))

    # then: `["chart","series"]` chart-series-required 하나뿐이다
    assert found == [(("chart", "series"), "chart-series-required")]


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_with_two_groups_and_a_series_parses(kind: str) -> None:
    """트리맵·선버스트는 그룹 2개와 계열을 받아들인다.

    테스트 코드: RC-009
    """
    # when: 계열을 지정해 검증한다 (전제: 그룹 컬럼이 2개인 정의)
    settings = _parse(TWO, raw_chart(kind, 0, [2], series=1))

    # then: 범주와 계열이 그대로다
    assert (settings.category, settings.series) == (0, 1)


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_with_one_group_parses_without_series(kind: str) -> None:
    """트리맵·선버스트는 그룹이 1개면 계열 없이 받아들인다.

    테스트 코드: RC-009
    """
    # when: 계열 없이 검증한다 (전제: 그룹 컬럼이 1개인 정의)
    settings = _parse(ONE, raw_chart(kind, 0, [1]))

    # then: 계열이 없다
    assert settings.series is None


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_rejects_swap_and_value_range(kind: str) -> None:
    """트리맵·선버스트는 행/열 전환과 값 범위를 거절한다.

    테스트 코드: RC-015, RC-019
    """
    # when: swap과 최소값을 준 차트를 검증한다
    found = _issue(ONE, raw_chart(kind, 0, [1], swap=True, value_min=0))

    # then: swap은 chart-swap-invalid, 최소값은 chart-range-invalid다
    assert sorted(found) == [
        (("chart", "swap"), "chart-swap-invalid"),
        (("chart", "value_min"), "chart-range-invalid"),
    ]


@pytest.mark.parametrize("kind", ["pareto", "waterfall", "funnel", "bubble", "histogram"])
def test_single_group_kinds_reject_a_series(kind: str) -> None:
    """그룹 하나만 쓰는 종류에 계열을 주면 chart-series-invalid다.

    테스트 코드: RC-010
    """
    # given: 종류에 맞는 값 목록과 범주(히스토그램은 null)
    values = [1, 2, 3] if kind == "bubble" else [1]
    category = None if kind == "histogram" else 0

    # when: 계열을 준 차트를 검증한다
    found = _issue(ONE, raw_chart(kind, category, values, series=0))

    # then: `["chart","series"]` chart-series-invalid 하나뿐이다
    assert found == [(("chart", "series"), "chart-series-invalid")]


@pytest.mark.parametrize("kind", PERCENT)
@pytest.mark.parametrize(
    ("key", "number"),
    [("value_min", -1), ("value_min", 101), ("value_max", -1), ("value_max", 120)],
)
def test_percent_kinds_reject_range_outside_0_100(kind: str, key: str, number: int) -> None:
    """100% 누적 5종은 0~100 밖의 범위를 거절한다.

    테스트 코드: RC-019
    """
    # when: 0~100 밖의 최소 또는 최대를 준 차트를 검증한다
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart(kind, 0, [1], **{key: number}))

    # then: 해당 키의 chart-range-invalid 하나이고 문구에 "0~100"이 있다
    (issue,) = caught.value.issues
    assert (issue.location, issue.code) == (("chart", key), "chart-range-invalid")
    assert "0~100" in issue.message


@pytest.mark.parametrize("kind", PERCENT)
def test_percent_kinds_accept_range_zero_to_hundred(kind: str) -> None:
    """100% 누적 5종은 0~100 범위를 받는다.

    테스트 코드: RC-019
    """
    # when: 0~100 범위로 검증한다
    settings = _parse(ONE, raw_chart(kind, 0, [1], value_min=0, value_max=100))

    # then: 범위가 그대로다
    assert (settings.value_min, settings.value_max) == (0, 100)


@pytest.mark.parametrize(
    "kind", ["stacked_line", "stacked_area", "radar", "stacked_horizontal_bar"]
)
def test_non_percent_new_kinds_accept_wide_ranges(kind: str) -> None:
    """100% 누적이 아닌 새 종류는 넓은 범위를 받는다.

    테스트 코드: RC-019
    """
    # when: -500~5000 범위로 검증한다
    settings = _parse(ONE, raw_chart(kind, 0, [1], value_min=-500, value_max=5000))

    # then: 범위가 그대로다
    assert (settings.value_min, settings.value_max) == (-500, 5000)


@pytest.mark.parametrize("kind", ["funnel", "treemap", "sunburst"])
@pytest.mark.parametrize("key", ["value_min", "value_max"])
def test_kinds_without_a_value_axis_reject_a_range(kind: str, key: str) -> None:
    """값 축이 없는 깔때기·트리맵·선버스트는 범위를 거절한다.

    테스트 코드: RC-019
    """
    # when: 범위를 준 차트를 검증한다
    found = _issue(ONE, raw_chart(kind, 0, [1], **{key: 10}))

    # then: 해당 키에 chart-range-invalid 하나뿐이다
    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("kind", ["pareto", "waterfall", "bubble", "histogram", "scatter_smooth"])
def test_kinds_with_a_value_axis_accept_a_range(kind: str) -> None:
    """값 축이 있는 파레토·폭포·거품형·히스토그램·곡선 분산형은 범위를 받는다.

    테스트 코드: RC-019
    """
    # given: 종류에 맞는 범주(히스토그램은 null)
    category = None if kind == "histogram" else 0

    # when: 0~10 범위로 검증한다
    settings = _parse(ONE, raw_chart(kind, category, _values_for(kind), value_min=0, value_max=10))

    # then: 범위가 그대로다
    assert (settings.value_min, settings.value_max) == (0, 10)


@pytest.mark.parametrize("kind", CARTESIAN)
def test_swap_is_accepted_for_cartesian_like_new_kinds(kind: str) -> None:
    """새 막대·꺾은선·영역·방사형은 행/열 전환을 받는다.

    테스트 코드: RC-015
    """
    # when: swap true로 검증한다
    settings = _parse(ONE, raw_chart(kind, 0, [1], swap=True))

    # then: swap이 켜진 채 통과한다
    assert settings.swap is True


@pytest.mark.parametrize(
    "kind", [*SCATTERS[1:], "bubble", "pareto", "waterfall", "funnel", "histogram"]
)
def test_swap_is_rejected_for_other_new_kinds(kind: str) -> None:
    """그 밖의 새 종류는 행/열 전환을 거절한다.

    테스트 코드: RC-015
    """
    # given: 종류에 맞는 범주(히스토그램은 null)
    category = None if kind == "histogram" else 0

    # when: swap을 켜고 검증한다
    found = _issue(ONE, raw_chart(kind, category, _values_for(kind), swap=True))

    # then: `["chart","swap"]` chart-swap-invalid 하나뿐이다
    assert found == [(("chart", "swap"), "chart-swap-invalid")]


@pytest.mark.parametrize("kind", [k for k in NEW_KINDS if k != "combo"])
def test_secondary_axis_on_non_combo_kinds_is_rejected(kind: str) -> None:
    """콤보가 아닌 새 종류는 보조 축을 거절한다.

    테스트 코드: RC-015
    """
    # when: 보조 축을 켠 차트를 검증한다
    found = _issue(ONE, _with(_minimal(kind), secondary_axis=True))

    # then: `["chart","secondary_axis"]` chart-secondary-invalid 하나뿐이다
    assert found == [(("chart", "secondary_axis"), "chart-secondary-invalid")]


def _with(chart: Any, **changes: Any) -> Any:  # noqa: ANN401 - RawChart
    import dataclasses  # noqa: PLC0415

    return dataclasses.replace(chart, **changes)
