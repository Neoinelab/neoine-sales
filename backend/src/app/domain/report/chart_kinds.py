"""차트 종류 33종과 종류별 규칙표. 프런트 `chartKinds.ts`도 같은 표를 쓴다(정본은 여기)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

CHART_VALUES_MAX: Final = 10  # 기존 SERIES_COLORS 10색과 같음


class ChartKind(StrEnum):
    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    STACKED_100_BAR = "stacked_100_bar"
    HORIZONTAL_BAR = "horizontal_bar"
    STACKED_HORIZONTAL_BAR = "stacked_horizontal_bar"
    STACKED_100_HORIZONTAL_BAR = "stacked_100_horizontal_bar"
    LINE = "line"
    LINE_MARKERS = "line_markers"
    STACKED_LINE = "stacked_line"
    STACKED_LINE_MARKERS = "stacked_line_markers"
    STACKED_100_LINE = "stacked_100_line"
    STACKED_100_LINE_MARKERS = "stacked_100_line_markers"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    AREA = "area"
    STACKED_AREA = "stacked_area"
    STACKED_100_AREA = "stacked_100_area"
    SCATTER = "scatter"
    SCATTER_SMOOTH_MARKERS = "scatter_smooth_markers"
    SCATTER_SMOOTH = "scatter_smooth"
    SCATTER_LINE_MARKERS = "scatter_line_markers"
    SCATTER_LINE = "scatter_line"
    BUBBLE = "bubble"
    RADAR = "radar"
    RADAR_MARKERS = "radar_markers"
    RADAR_FILLED = "radar_filled"
    TREEMAP = "treemap"
    SUNBURST = "sunburst"
    HISTOGRAM = "histogram"
    PARETO = "pareto"
    WATERFALL = "waterfall"
    FUNNEL = "funnel"
    COMBO = "combo"


class ChartOption(StrEnum):
    """종류가 허용하는 전용 옵션(저장 JSON의 키 이름과 같다)."""

    HISTOGRAM = "histogram"
    SHOW_TOTAL = "show_total"
    COMBO_SERIES = "combo_series"


@dataclass(frozen=True, slots=True)
class KindRule:
    """종류 하나가 허용하는 설정."""

    max_groups: int  # 쓸 수 있는 그룹핑 컬럼 수의 최대
    allows_series: bool
    values_min: int
    values_max: int
    allows_swap: bool
    allows_value_range: bool
    allows_secondary: bool
    percent_axis: bool = False  # value_min/max는 0~100
    min_groups: int = 1  # 히스토그램만 0
    uses_category: bool = True  # 히스토그램만 False(category는 null이어야 함)
    options: frozenset[ChartOption] = frozenset()

    def value_count_range(self, *, has_series: bool) -> tuple[int, int]:
        """계열이 있으면 값은 정확히 1개다."""
        return (1, 1) if has_series else (self.values_min, self.values_max)


_MANY = CHART_VALUES_MAX
_CARTESIAN = KindRule(2, True, 1, _MANY, True, True, False)
_PERCENT = KindRule(2, True, 1, _MANY, True, True, False, percent_axis=True)
_ROUND = KindRule(1, False, 1, 1, False, False, False)
_SCATTER = KindRule(1, False, 2, _MANY, False, True, False)
_SINGLE = KindRule(1, False, 1, 1, False, True, False)
_HIERARCHY = KindRule(2, True, 1, 1, False, False, False)
_NO_AXIS = KindRule(1, False, 1, 1, False, False, False)

KIND_RULES: Final[dict[ChartKind, KindRule]] = {
    **dict.fromkeys(
        [
            ChartKind.BAR,
            ChartKind.STACKED_BAR,
            ChartKind.HORIZONTAL_BAR,
            ChartKind.STACKED_HORIZONTAL_BAR,
            ChartKind.LINE,
            ChartKind.LINE_MARKERS,
            ChartKind.STACKED_LINE,
            ChartKind.STACKED_LINE_MARKERS,
            ChartKind.AREA,
            ChartKind.STACKED_AREA,
            ChartKind.RADAR,
            ChartKind.RADAR_MARKERS,
            ChartKind.RADAR_FILLED,
        ],
        _CARTESIAN,
    ),
    **dict.fromkeys(
        [
            ChartKind.STACKED_100_BAR,
            ChartKind.STACKED_100_HORIZONTAL_BAR,
            ChartKind.STACKED_100_LINE,
            ChartKind.STACKED_100_LINE_MARKERS,
            ChartKind.STACKED_100_AREA,
        ],
        _PERCENT,
    ),
    ChartKind.PIE: _ROUND,
    ChartKind.DOUGHNUT: _ROUND,
    **dict.fromkeys(
        [
            ChartKind.SCATTER,
            ChartKind.SCATTER_SMOOTH_MARKERS,
            ChartKind.SCATTER_SMOOTH,
            ChartKind.SCATTER_LINE_MARKERS,
            ChartKind.SCATTER_LINE,
        ],
        _SCATTER,
    ),
    ChartKind.BUBBLE: KindRule(1, False, 3, 3, False, True, False),
    ChartKind.TREEMAP: _HIERARCHY,
    ChartKind.SUNBURST: _HIERARCHY,
    ChartKind.HISTOGRAM: KindRule(
        2,
        False,
        1,
        1,
        False,
        True,
        False,
        min_groups=0,
        uses_category=False,
        options=frozenset({ChartOption.HISTOGRAM}),
    ),
    ChartKind.PARETO: _SINGLE,
    ChartKind.WATERFALL: KindRule(
        1, False, 1, 1, False, True, False, options=frozenset({ChartOption.SHOW_TOTAL})
    ),
    ChartKind.FUNNEL: _NO_AXIS,
    ChartKind.COMBO: KindRule(
        1, False, 2, _MANY, False, True, True, options=frozenset({ChartOption.COMBO_SERIES})
    ),
}
