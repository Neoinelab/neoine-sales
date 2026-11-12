"""차트 종류 33종과 규칙표 `KIND_RULES`를 명세 표(RC-R1, RC-R2) 그대로 고정한다.

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
    """종류 키는 명세의 33개와 정확히 같다.

    테스트 코드: RC-001
    """
    # when: 종류 enum의 값을 모은다
    values = {k.value for k in ChartKind}

    # then: 33개이고 옛 10개와 새 23개를 합친 것과 같다
    assert len(values) == 33
    assert values == LEGACY | NEW


def test_the_ten_existing_kind_values_keep_their_names() -> None:
    """옛 10개 종류 키와 주요 이름은 그대로다.

    테스트 코드: RC-001
    """
    # when: 종류 enum의 값을 모은다
    values = {k.value for k in ChartKind}

    # then: 옛 10개를 모두 포함하고 누적 종류 이름이 바뀌지 않았다
    assert values >= LEGACY
    assert ChartKind.STACKED_BAR.value == "stacked_bar"
    assert ChartKind.STACKED_100_BAR.value == "stacked_100_bar"


def test_chart_option_values_are_the_three_stored_keys() -> None:
    """종류 전용 옵션 키는 histogram·show_total·combo_series 셋이다.

    테스트 코드: RC-001
    """
    # when: 옵션 enum의 값을 모은다
    values = {o.value for o in ChartOption}

    # then: 저장 키 세 개와 같다
    assert values == {"histogram", "show_total", "combo_series"}


def test_every_kind_has_exactly_one_rule() -> None:
    """모든 종류가 규칙표에 규칙을 하나씩 가진다.

    테스트 코드: RC-002
    """
    # when: 규칙표의 키를 모은다
    kinds = set(KIND_RULES)

    # then: 종류 enum 전체와 같다
    assert kinds == set(ChartKind)


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_kind_rule_matches_the_planned_table(kind: str) -> None:
    """종류마다 규칙표의 값이 명세 표와 같다.

    테스트 코드: RC-002
    """
    # when: 종류의 규칙을 읽는다
    rule = KIND_RULES[ChartKind(kind)]

    # then: 명세 표의 규칙과 같다
    assert rule == EXPECTED[kind]


def test_expected_table_covers_every_kind() -> None:
    """기대 표 자체가 33개 종류를 빠짐없이 덮는다.

    테스트 코드: RC-002
    """
    # when: 기대 표의 키를 모은다
    kinds = set(EXPECTED)

    # then: 옛 10개와 새 23개를 합친 것과 같다
    assert kinds == LEGACY | NEW


def test_only_histogram_allows_zero_groups_and_skips_the_category() -> None:
    """그룹 0개를 허용하고 범주를 쓰지 않는 종류는 히스토그램뿐이다.

    테스트 코드: RC-002
    """
    # when: 최소 그룹 수가 0인 종류와 범주를 쓰지 않는 종류를 모은다
    no_min = {k.value for k, r in KIND_RULES.items() if r.min_groups == 0}
    no_category = {k.value for k, r in KIND_RULES.items() if not r.uses_category}

    # then: 둘 다 히스토그램뿐이다
    assert no_min == {"histogram"}
    assert no_category == {"histogram"}


def test_only_combo_allows_a_secondary_axis_flag() -> None:
    """보조 축 켜기를 허용하는 종류는 콤보뿐이다.

    테스트 코드: RC-002
    """
    # when: 보조 축을 허용하는 종류를 모은다
    kinds = {k.value for k, r in KIND_RULES.items() if r.allows_secondary}

    # then: 콤보뿐이다
    assert kinds == {"combo"}


def test_percent_axis_belongs_to_the_five_hundred_percent_kinds() -> None:
    """0~100 축을 쓰는 종류는 100% 누적 5종뿐이다.

    테스트 코드: RC-002
    """
    # when: 퍼센트 축을 쓰는 종류를 모은다
    percent = {k.value for k, r in KIND_RULES.items() if r.percent_axis}

    # then: 100% 누적 다섯 종류와 같다
    assert percent == {
        "stacked_100_bar",
        "stacked_100_horizontal_bar",
        "stacked_100_line",
        "stacked_100_line_markers",
        "stacked_100_area",
    }


def test_value_count_range_is_exactly_one_when_a_series_is_used() -> None:
    """계열을 쓰면 값 개수는 정확히 1개이고 쓰지 않으면 종류 범위 그대로다.

    테스트 코드: RC-002
    """
    # when: 막대와 거품형의 값 개수 범위를 계열 유무별로 읽는다
    bar_with_series = KIND_RULES[ChartKind.BAR].value_count_range(has_series=True)
    bar_without = KIND_RULES[ChartKind.BAR].value_count_range(has_series=False)
    bubble = KIND_RULES[ChartKind.BUBBLE].value_count_range(has_series=False)

    # then: 계열이 있으면 (1, 1), 없으면 종류 범위다
    assert bar_with_series == (1, 1)
    assert bar_without == (1, 10)
    assert bubble == (3, 3)
