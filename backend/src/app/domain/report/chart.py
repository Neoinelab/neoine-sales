"""차트 설정 값 객체: 범례, 전용 옵션, 검증을 통과한 설정. 종류·규칙표는 `chart_kinds`."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from app.domain.report.raw import RawChart

if TYPE_CHECKING:
    from app.domain.report.chart_kinds import ChartKind

CHART_TEXT_MAX: Final = 100  # LABEL_MAX와 같음
PERCENT_MAX: Final = 100
SAFE_INTEGER_MAX: Final = 2**53 - 1
HISTOGRAM_BINS_MAX: Final = 100
HISTOGRAM_BIN_KEYS: Final = frozenset(
    {"bin_mode", "bin_count", "bin_width", "overflow", "underflow"}
)


class LegendPosition(StrEnum):
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    NONE = "none"


class BinMode(StrEnum):
    AUTO = "auto"
    COUNT = "count"
    WIDTH = "width"


class ComboSeriesType(StrEnum):
    COLUMN = "column"
    STACKED_COLUMN = "stacked_column"
    LINE = "line"
    LINE_MARKERS = "line_markers"
    AREA = "area"
    STACKED_AREA = "stacked_area"


@dataclass(frozen=True, slots=True)
class HistogramBins:
    """히스토그램 구간 설정(검증을 마친 값)."""

    mode: BinMode
    count: int | None
    width: int | float | None
    overflow: int | float | None
    underflow: int | float | None

    def to_json(self) -> dict[str, object]:
        return {
            "bin_mode": self.mode.value,
            "bin_count": self.count,
            "bin_width": self.width,
            "overflow": self.overflow,
            "underflow": self.underflow,
        }


@dataclass(frozen=True, slots=True)
class ComboSeries:
    """콤보 계열 하나의 종류와 보조 축 여부."""

    type: ComboSeriesType
    secondary: bool

    def to_json(self) -> dict[str, object]:
        return {"type": self.type.value, "secondary": self.secondary}


def auto_bins_json() -> dict[str, object]:
    """구간 설정이 없는 히스토그램의 기본값(자동)."""
    return HistogramBins(BinMode.AUTO, None, None, None, None).to_json()


def legacy_combo_series(count: int, *, secondary: bool) -> tuple[ComboSeries, ...]:
    """계열별 설정이 없던 옛 콤보: 첫 값 열은 막대, 나머지는 꺾은선(보조 축은 꺾은선만)."""
    first = ComboSeries(ComboSeriesType.COLUMN, secondary=False)
    line = ComboSeries(ComboSeriesType.LINE, secondary=secondary)
    return (first, *([line] * max(count - 1, 0)))[:count]


def legacy_combo_series_json(count: int, *, secondary: bool) -> list[dict[str, object]]:
    return [s.to_json() for s in legacy_combo_series(count, secondary=secondary)]


@dataclass(frozen=True, slots=True)
class ChartSettings:
    """검증·정규화를 마친 차트 설정. 컬럼은 정의 `columns`의 index로 가리킨다."""

    kind: ChartKind
    category: int | None  # 히스토그램만 None
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
    histogram: HistogramBins | None = None
    show_total: bool = False
    combo_series: tuple[ComboSeries, ...] | None = None

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
            histogram=self.histogram.to_json() if self.histogram else None,
            show_total=self.show_total,
            combo_series=[s.to_json() for s in self.combo_series] if self.combo_series else None,
        )
