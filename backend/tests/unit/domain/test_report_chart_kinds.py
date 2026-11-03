"""차트 종류 33종과 규칙표 `KIND_RULES` (Excel 확장 AC2·3·5): 계획 "설계 2" 표를 그대로 고정한다.

프런트 `chartKinds.ts`도 같은 표를 기대값으로 고정한다(두 벌이 어긋나지 않게).
"""

import pytest
from app.domain.report.chart_kinds import KIND_RULES, ChartKind, ChartOption, KindRule

LEGACY = {
    "bar",
    "horizontal_bar",
    "stacked_bar",
    "stacked_100_bar",
    "line",
    "area",
    "pie",
    "doughnut",
    "scatter",
    "combo",
}
NEW = {
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
}
NO_OPTIONS: frozenset[ChartOption] = frozenset()


def _rule(  # noqa: PLR0913
    max_groups: int,
    allows_series: bool,
    values: tuple[int, int],
    *,
    swap: bool = False,
    value_range: bool = False,
    secondary: bool = False,
    percent: bool = False,
    min_groups: int = 1,
    uses_category: bool = True,
    options: frozenset[ChartOption] = NO_OPTIONS,
) -> KindRule:
    return KindRule(
        max_groups=max_groups,
        allows_series=allows_series,
        values_min=values[0],
        values_max=values[1],
        allows_swap=swap,
        allows_value_range=value_range,
        allows_secondary=secondary,
        percent_axis=percent,
        min_groups=min_groups,
        uses_category=uses_category,
        options=options,
    )


_CARTESIAN = _rule(2, True, (1, 10), swap=True, value_range=True)
_PERCENT = _rule(2, True, (1, 10), swap=True, value_range=True, percent=True)
_ROUND = _rule(1, False, (1, 1))
_SCATTER = _rule(1, False, (2, 10), value_range=True)
_SINGLE_VALUE = _rule(1, False, (1, 1), value_range=True)
_HIERARCHY = _rule(2, True, (1, 1))

EXPECTED: dict[str, KindRule] = {
    **dict.fromkeys(["bar", "stacked_bar", "horizontal_bar", "stacked_horizontal_bar"], _CARTESIAN),
    **dict.fromkeys(["stacked_100_bar", "stacked_100_horizontal_bar"], _PERCENT),
    **dict.fromkeys(["line", "line_markers", "stacked_line", "stacked_line_markers"], _CARTESIAN),
    **dict.fromkeys(["stacked_100_line", "stacked_100_line_markers"], _PERCENT),
    **dict.fromkeys(["area", "stacked_area"], _CARTESIAN),
    "stacked_100_area": _PERCENT,
    **dict.fromkeys(["pie", "doughnut"], _ROUND),
    **dict.fromkeys(
        [
            "scatter",
            "scatter_smooth_markers",
            "scatter_smooth",
            "scatter_line_markers",
            "scatter_line",
        ],
        _SCATTER,
    ),
    "bubble": _rule(1, False, (3, 3), value_range=True),
    **dict.fromkeys(["radar", "radar_markers", "radar_filled"], _CARTESIAN),
    **dict.fromkeys(["treemap", "sunburst"], _HIERARCHY),
    "histogram": _rule(
        2,
        False,
        (1, 1),
        value_range=True,
        min_groups=0,
        uses_category=False,
        options=frozenset({ChartOption.HISTOGRAM}),
    ),
    "pareto": _SINGLE_VALUE,
    "waterfall": _rule(
        1, False, (1, 1), value_range=True, options=frozenset({ChartOption.SHOW_TOTAL})
    ),
    "funnel": _rule(1, False, (1, 1)),
    "combo": _rule(
        1,
        False,
        (2, 10),
        value_range=True,
        secondary=True,
        options=frozenset({ChartOption.COMBO_SERIES}),
    ),
}


def test_chart_kind_values_match_the_planned_33() -> None:
    values = {k.value for k in ChartKind}

    assert len(values) == 33
    assert values == LEGACY | NEW


def test_the_ten_existing_kind_values_keep_their_names() -> None:
    assert {k.value for k in ChartKind} >= LEGACY
    assert ChartKind.STACKED_BAR.value == "stacked_bar"
    assert ChartKind.STACKED_100_BAR.value == "stacked_100_bar"


def test_every_kind_has_exactly_one_rule() -> None:
    assert set(KIND_RULES) == set(ChartKind)


def test_chart_option_values_are_the_three_stored_keys() -> None:
    assert {o.value for o in ChartOption} == {"histogram", "show_total", "combo_series"}


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_kind_rule_matches_the_planned_table(kind: str) -> None:
    assert KIND_RULES[ChartKind(kind)] == EXPECTED[kind]


def test_expected_table_covers_every_kind() -> None:
    assert set(EXPECTED) == LEGACY | NEW


def test_only_histogram_allows_zero_groups_and_skips_the_category() -> None:
    no_min = {k.value for k, r in KIND_RULES.items() if r.min_groups == 0}
    no_category = {k.value for k, r in KIND_RULES.items() if not r.uses_category}

    assert no_min == {"histogram"}
    assert no_category == {"histogram"}


def test_only_combo_allows_a_secondary_axis_flag() -> None:
    assert {k.value for k, r in KIND_RULES.items() if r.allows_secondary} == {"combo"}


def test_percent_axis_belongs_to_the_five_hundred_percent_kinds() -> None:
    percent = {k.value for k, r in KIND_RULES.items() if r.percent_axis}

    assert percent == {
        "stacked_100_bar",
        "stacked_100_horizontal_bar",
        "stacked_100_line",
        "stacked_100_line_markers",
        "stacked_100_area",
    }


def test_value_count_range_is_exactly_one_when_a_series_is_used() -> None:
    assert KIND_RULES[ChartKind.BAR].value_count_range(has_series=True) == (1, 1)
    assert KIND_RULES[ChartKind.BAR].value_count_range(has_series=False) == (1, 10)
    assert KIND_RULES[ChartKind.BUBBLE].value_count_range(has_series=False) == (3, 3)
