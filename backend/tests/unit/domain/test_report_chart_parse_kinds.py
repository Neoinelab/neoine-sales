"""새 차트 종류 23종의 검증 `parse_chart` (Excel 확장 AC2·3·5·6·7·9·10).

기존 10종은 `test_report_chart_parse.py`가 고정한다. 여기서는 새 종류가 규칙표대로
받아들여지고, 어긋나면 지정한 코드·위치(`("chart", ...)`)로 거절되는지 본다.
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


# ---- 받아들이기 (AC2) ----


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_each_new_kind_with_valid_columns_parses(kind: str) -> None:
    settings = _parse(ONE, _minimal(kind))

    assert settings.kind == ChartKind(kind)
    assert settings.category == (None if kind == "histogram" else 0)
    assert settings.series is None


@pytest.mark.parametrize(
    "kind", ["stacked_horizontal_bar", "stacked_line", "radar", "stacked_area"]
)
def test_cartesian_like_new_kinds_accept_two_groups_with_a_series(kind: str) -> None:
    settings = _parse(TWO, raw_chart(kind, 0, [2], series=1, swap=True))

    assert (settings.category, settings.series, settings.values, settings.swap) == (
        0,
        1,
        (2,),
        True,
    )


# ---- 그룹핑 수 (AC3) ----


@pytest.mark.parametrize("kind", ONE_GROUP_ONLY)
def test_kind_with_too_many_groups_reports_chart_kind_groups(kind: str) -> None:
    chart = raw_chart(kind, 0, [v + 1 for v in _values_for(kind)])  # TWO의 값 컬럼은 2부터

    found = _issue(TWO, chart)

    assert (("chart", "kind"), "chart-kind-groups") in found


def test_chart_kind_groups_message_is_common_to_every_kind() -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(TWO, raw_chart("pareto", 0, [2]))

    (issue,) = [i for i in caught.value.issues if i.code == "chart-kind-groups"]
    assert issue.message == "이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다"


@pytest.mark.parametrize("kind", ["bar", "line_markers", "stacked_area", "radar", "treemap"])
def test_ungrouped_non_histogram_reports_needs_grouping(kind: str) -> None:
    found = _issue(UNGROUPED, raw_chart(kind, 0, [1]))

    assert found == [(("chart",), "chart-needs-grouping")]


def test_three_groups_stay_too_many_for_the_histogram() -> None:
    found = _issue(chart_definition(3, 2), raw_chart("histogram", None, [3]))

    assert found == [(("chart",), "chart-too-many-groups")]


# ---- 히스토그램: 범주 없음·그룹핑 없는 리포트 (AC10) ----


def test_ungrouped_histogram_accepts_a_number_column() -> None:
    settings = _parse(UNGROUPED, raw_chart("histogram", None, [1]))

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
    found = _issue(UNGROUPED, raw_chart("histogram", None, [0]))

    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_ungrouped_histogram_rejects_a_missing_column() -> None:
    found = _issue(UNGROUPED, raw_chart("histogram", None, [99]))

    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_ungrouped_histogram_needs_exactly_one_value() -> None:
    found = _issue(UNGROUPED, raw_chart("histogram", None, [1, 1]))

    assert (("chart", "values"), "chart-values-count") in found


def test_grouped_histogram_accepts_an_aggregate_column() -> None:
    settings = _parse(ONE, raw_chart("histogram", None, [2]))

    assert (settings.category, settings.values) == (None, (2,))


def test_grouped_histogram_rejects_a_group_column_as_the_value() -> None:
    found = _issue(ONE, raw_chart("histogram", None, [0]))

    assert found == [(("chart", "values", 0), "chart-value-invalid")]


def test_histogram_with_category_reports_category_invalid() -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart("histogram", 0, [1]))

    (issue,) = caught.value.issues
    assert issue.location == ("chart", "category")
    assert issue.code == "chart-category-invalid"
    assert issue.message == "이 차트는 범주 열을 쓰지 않습니다"


def test_non_histogram_with_null_category_reports_category_invalid() -> None:
    found = _issue(ONE, raw_chart("pareto", None, [1]))

    assert found == [(("chart", "category"), "chart-category-invalid")]


# ---- 분산형·거품형 값 개수 (AC6·7) ----


@pytest.mark.parametrize("kind", SCATTERS)
@pytest.mark.parametrize("count", [2, 10])
def test_scatter_family_accepts_two_to_ten_values(kind: str, count: int) -> None:
    settings = _parse(ONE, raw_chart(kind, 0, list(range(1, count + 1))))

    assert len(settings.values) == count


@pytest.mark.parametrize("kind", SCATTERS)
def test_scatter_with_one_value_reports_count(kind: str) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart(kind, 0, [1]))

    (issue,) = caught.value.issues
    assert (issue.location, issue.code) == (("chart", "values"), "chart-values-count")
    assert "2~10개" in issue.message


@pytest.mark.parametrize("kind", SCATTERS)
def test_scatter_with_eleven_values_reports_count(kind: str) -> None:
    found = _issue(ONE, raw_chart(kind, 0, list(range(1, 12))))

    assert found == [(("chart", "values"), "chart-values-count")]


@pytest.mark.parametrize("values", [[1, 2], [1, 2, 3, 4]])
def test_bubble_rejects_anything_but_three_values(values: list[int]) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart("bubble", 0, values))

    (issue,) = caught.value.issues
    assert (issue.location, issue.code) == (("chart", "values"), "chart-values-count")
    assert "3개" in issue.message


def test_bubble_accepts_exactly_three_values() -> None:
    assert _parse(ONE, raw_chart("bubble", 0, [1, 2, 3])).values == (1, 2, 3)


# ---- 단일 값 종류 ----


@pytest.mark.parametrize(
    "kind", ["pareto", "waterfall", "funnel", "treemap", "sunburst", "histogram"]
)
def test_single_value_kinds_reject_two_values(kind: str) -> None:
    category = None if kind == "histogram" else 0

    found = _issue(ONE, raw_chart(kind, category, [1, 2]))

    assert found == [(("chart", "values"), "chart-values-count")]


# ---- 트리맵·선버스트 계열 (AC9) ----


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_with_two_groups_requires_a_series(kind: str) -> None:
    found = _issue(TWO, raw_chart(kind, 0, [2]))

    assert found == [(("chart", "series"), "chart-series-required")]


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_with_two_groups_and_a_series_parses(kind: str) -> None:
    settings = _parse(TWO, raw_chart(kind, 0, [2], series=1))

    assert (settings.category, settings.series) == (0, 1)


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_with_one_group_parses_without_series(kind: str) -> None:
    assert _parse(ONE, raw_chart(kind, 0, [1])).series is None


@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_hierarchy_rejects_swap_and_value_range(kind: str) -> None:
    found = _issue(ONE, raw_chart(kind, 0, [1], swap=True, value_min=0))

    assert sorted(found) == [
        (("chart", "swap"), "chart-swap-invalid"),
        (("chart", "value_min"), "chart-range-invalid"),
    ]


@pytest.mark.parametrize("kind", ["pareto", "waterfall", "funnel", "bubble", "histogram"])
def test_single_group_kinds_reject_a_series(kind: str) -> None:
    values = [1, 2, 3] if kind == "bubble" else [1]
    category = None if kind == "histogram" else 0

    found = _issue(ONE, raw_chart(kind, category, values, series=0))

    assert found == [(("chart", "series"), "chart-series-invalid")]


# ---- 100% 누적 축 범위 (AC5) ----


@pytest.mark.parametrize("kind", PERCENT)
@pytest.mark.parametrize(
    ("key", "number"),
    [("value_min", -1), ("value_min", 101), ("value_max", -1), ("value_max", 120)],
)
def test_percent_kinds_reject_range_outside_0_100(kind: str, key: str, number: int) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        _parse(ONE, raw_chart(kind, 0, [1], **{key: number}))

    (issue,) = caught.value.issues
    assert (issue.location, issue.code) == (("chart", key), "chart-range-invalid")
    assert "0~100" in issue.message


@pytest.mark.parametrize("kind", PERCENT)
def test_percent_kinds_accept_range_zero_to_hundred(kind: str) -> None:
    settings = _parse(ONE, raw_chart(kind, 0, [1], value_min=0, value_max=100))

    assert (settings.value_min, settings.value_max) == (0, 100)


@pytest.mark.parametrize(
    "kind", ["stacked_line", "stacked_area", "radar", "stacked_horizontal_bar"]
)
def test_non_percent_new_kinds_accept_wide_ranges(kind: str) -> None:
    settings = _parse(ONE, raw_chart(kind, 0, [1], value_min=-500, value_max=5000))

    assert (settings.value_min, settings.value_max) == (-500, 5000)


@pytest.mark.parametrize("kind", ["funnel", "treemap", "sunburst"])
@pytest.mark.parametrize("key", ["value_min", "value_max"])
def test_kinds_without_a_value_axis_reject_a_range(kind: str, key: str) -> None:
    found = _issue(ONE, raw_chart(kind, 0, [1], **{key: 10}))

    assert found == [(("chart", key), "chart-range-invalid")]


@pytest.mark.parametrize("kind", ["pareto", "waterfall", "bubble", "histogram", "scatter_smooth"])
def test_kinds_with_a_value_axis_accept_a_range(kind: str) -> None:
    category = None if kind == "histogram" else 0

    settings = _parse(ONE, raw_chart(kind, category, _values_for(kind), value_min=0, value_max=10))

    assert (settings.value_min, settings.value_max) == (0, 10)


# ---- 행/열 전환·보조 축 (AC3) ----


@pytest.mark.parametrize("kind", CARTESIAN)
def test_swap_is_accepted_for_cartesian_like_new_kinds(kind: str) -> None:
    assert _parse(ONE, raw_chart(kind, 0, [1], swap=True)).swap is True


@pytest.mark.parametrize(
    "kind", [*SCATTERS[1:], "bubble", "pareto", "waterfall", "funnel", "histogram"]
)
def test_swap_is_rejected_for_other_new_kinds(kind: str) -> None:
    category = None if kind == "histogram" else 0

    found = _issue(ONE, raw_chart(kind, category, _values_for(kind), swap=True))

    assert found == [(("chart", "swap"), "chart-swap-invalid")]


@pytest.mark.parametrize("kind", [k for k in NEW_KINDS if k != "combo"])
def test_secondary_axis_on_non_combo_kinds_is_rejected(kind: str) -> None:
    found = _issue(ONE, _with(_minimal(kind), secondary_axis=True))

    assert found == [(("chart", "secondary_axis"), "chart-secondary-invalid")]


def _with(chart: Any, **changes: Any) -> Any:  # noqa: ANN401 - RawChart
    import dataclasses  # noqa: PLC0415

    return dataclasses.replace(chart, **changes)
