"""차트 설정 값 객체: 종류·범례, 종류별 규칙표, 검증을 통과한 설정."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from app.domain.report.raw import RawChart

CHART_VALUES_MAX: Final = 10  # 기존 SERIES_COLORS 10색과 같음
CHART_TEXT_MAX: Final = 100  # LABEL_MAX와 같음
PERCENT_MAX: Final = 100
SAFE_INTEGER_MAX: Final = 2**53 - 1


class ChartKind(StrEnum):
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    STACKED_BAR = "stacked_bar"
    STACKED_100_BAR = "stacked_100_bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    SCATTER = "scatter"
    COMBO = "combo"


class LegendPosition(StrEnum):
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class KindRule:
    """종류 하나가 허용하는 설정. 프런트 `chartKinds.ts`도 같은 표를 쓴다."""

    max_groups: int  # 쓸 수 있는 그룹핑 컬럼 수의 최대
    allows_series: bool
    values_min: int
    values_max: int
    allows_swap: bool
    allows_value_range: bool
    allows_secondary: bool
    percent_axis: bool = False  # value_min/max는 0~100

    def value_count_range(self, *, has_series: bool) -> tuple[int, int]:
        """계열이 있으면 값은 정확히 1개다."""
        return (1, 1) if has_series else (self.values_min, self.values_max)


_BAR_LIKE = KindRule(2, True, 1, CHART_VALUES_MAX, True, True, False)
_ROUND = KindRule(1, False, 1, 1, False, False, False)

KIND_RULES: Final[dict[ChartKind, KindRule]] = {
    ChartKind.BAR: _BAR_LIKE,
    ChartKind.HORIZONTAL_BAR: _BAR_LIKE,
    ChartKind.STACKED_BAR: _BAR_LIKE,
    ChartKind.STACKED_100_BAR: KindRule(2, True, 1, CHART_VALUES_MAX, True, True, False, True),
    ChartKind.LINE: _BAR_LIKE,
    ChartKind.AREA: _BAR_LIKE,
    ChartKind.PIE: _ROUND,
    ChartKind.DOUGHNUT: _ROUND,
    ChartKind.SCATTER: KindRule(1, False, 2, 2, False, True, False),
    ChartKind.COMBO: KindRule(1, False, 2, CHART_VALUES_MAX, False, True, True),
}


@dataclass(frozen=True, slots=True)
class ChartSettings:
    """검증·정규화를 마친 차트 설정. 컬럼은 정의 `columns`의 index로 가리킨다."""

    kind: ChartKind
    category: int
    series: int | None
    values: tuple[int, ...]
    swap: bool
    title: str
    legend: LegendPosition
    data_labels: bool
    category_axis_title: str
    value_axis_title: str
    value_min: int | float | None
    value_max: int | float | None
    secondary_axis: bool

    def to_raw(self) -> RawChart:
        """저장할 정규화된 원시 차트(JSON에 그대로 쓸 수 있는 값)."""
        return RawChart(
            kind=self.kind.value,
            category=self.category,
            values=list(self.values),
            series=self.series,
            swap=self.swap,
            title=self.title,
            legend=self.legend.value,
            data_labels=self.data_labels,
            category_axis_title=self.category_axis_title,
            value_axis_title=self.value_axis_title,
            value_min=self.value_min,
            value_max=self.value_max,
            secondary_axis=self.secondary_axis,
        )
