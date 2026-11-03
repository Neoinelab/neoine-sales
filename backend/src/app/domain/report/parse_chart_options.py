"""차트 전용 옵션(히스토그램 구간·폭포 합계·콤보 계열별 설정)의 검증과 정규화.

허용 여부는 종류의 `KindRule.options`가 정하고, 여기서는 값의 형식만 판정한다.
"""

import math
from typing import TYPE_CHECKING

from app.domain.report.chart import (
    HISTOGRAM_BIN_KEYS,
    HISTOGRAM_BINS_MAX,
    SAFE_INTEGER_MAX,
    BinMode,
    ComboSeries,
    ComboSeriesType,
    HistogramBins,
    legacy_combo_series,
)
from app.domain.report.chart_kinds import CHART_VALUES_MAX, ChartOption, KindRule
from app.domain.report.parse_columns import enum_member

if TYPE_CHECKING:
    from app.domain.report.errors import IssueLog

_COMBO_ITEM_KEYS = frozenset({"type", "secondary"})
_UNUSED = "이 구간 방식에서는 비워 두세요"
_HIST = ("chart", "histogram")
_COMBO = ("chart", "combo_series")


def is_bounded_number(raw: object) -> bool:
    """bool을 뺀 int·float이고 유한하며 절댓값이 2^53-1 이하."""
    if type(raw) is int:
        return abs(raw) <= SAFE_INTEGER_MAX  # float 변환 전에 판정(OverflowError 방지)
    return type(raw) is float and math.isfinite(raw) and abs(raw) <= SAFE_INTEGER_MAX


def _allowed(rule: KindRule | None, option: ChartOption) -> bool | None:
    """알려진 종류면 허용 여부, 종류를 모르면 None(판정하지 않음)."""
    return None if rule is None else option in rule.options


def parse_histogram(raw: object, rule: KindRule | None, log: IssueLog) -> HistogramBins | None:
    allowed = _allowed(rule, ChartOption.HISTOGRAM)
    if allowed is not True:
        if allowed is False and raw is not None:
            log.add(_HIST, "chart-option-invalid", "이 차트는 이 옵션을 쓰지 않습니다")
        return None
    if raw is None:
        return HistogramBins(BinMode.AUTO, None, None, None, None)
    if not isinstance(raw, dict) or set(raw) != HISTOGRAM_BIN_KEYS:
        log.add(_HIST, "chart-histogram-invalid", "구간 설정 형식이 올바르지 않습니다")
        return None
    return _bins(raw, log)


def _bins(raw: dict[str, object], log: IssueLog) -> HistogramBins | None:
    mode = enum_member(BinMode, raw["bin_mode"])
    if mode is None:
        message = "구간 방식은 auto·count·width 중 하나입니다"
        log.add((*_HIST, "bin_mode"), "chart-histogram-invalid", message)
        return None
    before = len(log.items)
    count, width = raw["bin_count"], raw["bin_width"]
    if mode is BinMode.COUNT:
        _count_ok(count, log)
        _unused(width, "bin_width", log)
    elif mode is BinMode.WIDTH:
        _width_ok(width, log)
        _unused(count, "bin_count", log)
    else:
        _unused(count, "bin_count", log)
        _unused(width, "bin_width", log)
    over = _side(raw["overflow"], "overflow", log)
    under = _side(raw["underflow"], "underflow", log)
    if over is not None and under is not None and under >= over:
        message = "오버플로 구간은 언더플로 구간보다 커야 합니다"
        log.add((*_HIST, "overflow"), "chart-range-order", message)
    if len(log.items) > before:
        return None
    return HistogramBins(
        mode,
        count if mode is BinMode.COUNT else None,  # type: ignore[arg-type]
        width if mode is BinMode.WIDTH else None,  # type: ignore[arg-type]
        over,
        under,
    )


def _count_ok(count: object, log: IssueLog) -> None:
    if type(count) is not int or not 1 <= count <= HISTOGRAM_BINS_MAX:
        log.add((*_HIST, "bin_count"), "chart-histogram-invalid", "구간 수는 1~100의 정수입니다")


def _width_ok(width: object, log: IssueLog) -> None:
    if not is_bounded_number(width) or width <= 0:  # type: ignore[operator]
        message = "구간 너비는 0보다 큰 숫자입니다"
        log.add((*_HIST, "bin_width"), "chart-histogram-invalid", message)


def _unused(value: object, key: str, log: IssueLog) -> None:
    if value is not None:
        log.add((*_HIST, key), "chart-histogram-invalid", _UNUSED)


def _side(value: object, key: str, log: IssueLog) -> int | float | None:
    if value is None:
        return None
    if not is_bounded_number(value):
        log.add((*_HIST, key), "chart-histogram-invalid", "숫자를 입력하세요")
        return None
    return value  # type: ignore[return-value]


def parse_show_total(raw: object, rule: KindRule | None, log: IssueLog) -> bool:
    location = ("chart", "show_total")
    if type(raw) is not bool:
        log.add(location, "chart-flag-invalid", "켜기·끄기 값이어야 합니다")
        return False
    if raw and _allowed(rule, ChartOption.SHOW_TOTAL) is False:
        log.add(location, "chart-option-invalid", "이 차트는 이 옵션을 쓰지 않습니다")
    return raw


def parse_combo_series(
    raw: object,
    rule: KindRule | None,
    value_count: int | None,
    secondary_axis: object,
    log: IssueLog,
) -> tuple[ComboSeries, ...] | None:
    """콤보면 계열별 설정(없으면 옛 규칙으로 채움), 다른 종류면 None."""
    allowed = _allowed(rule, ChartOption.COMBO_SERIES)
    if allowed is not True:
        if allowed is False and raw is not None:
            log.add(_COMBO, "chart-option-invalid", "이 차트는 이 옵션을 쓰지 않습니다")
        return None
    if value_count is None:
        return None
    if raw is None:
        return legacy_combo_series(value_count, secondary=secondary_axis is True)
    return _explicit(raw, value_count, secondary_axis, log)


def _explicit(
    raw: object, value_count: int, secondary_axis: object, log: IssueLog
) -> tuple[ComboSeries, ...] | None:
    if not isinstance(raw, list):
        log.add(_COMBO, "chart-combo-invalid", "계열 설정은 목록이어야 합니다")
        return None
    if len(raw) > CHART_VALUES_MAX or len(raw) != value_count:
        log.add(_COMBO, "chart-combo-invalid", "계열 설정 수가 값 열 수와 같아야 합니다")
        return None
    items = _items(raw, log)
    return None if items is None else _check_secondary(items, secondary_axis, log)


def _items(raw: list[object], log: IssueLog) -> list[ComboSeries] | None:
    items: list[ComboSeries] = []
    for i, item in enumerate(raw):
        series = _item(item)
        if series is None:
            log.add((*_COMBO, i), "chart-combo-invalid", "계열 종류와 보조 축을 확인하세요")
        else:
            items.append(series)
    return items if len(items) == len(raw) else None


def _item(item: object) -> ComboSeries | None:
    if not isinstance(item, dict) or set(item) != _COMBO_ITEM_KEYS:
        return None
    kind = enum_member(ComboSeriesType, item["type"])
    if kind is None or type(item["secondary"]) is not bool:
        return None
    return ComboSeries(kind, secondary=item["secondary"])


def _check_secondary(
    items: list[ComboSeries], secondary_axis: object, log: IssueLog
) -> tuple[ComboSeries, ...] | None:
    if items and all(s.secondary for s in items):
        log.add(_COMBO, "chart-combo-secondary-all", "모든 계열을 보조 축에 둘 수 없습니다")
        return None
    if type(secondary_axis) is bool and secondary_axis != any(s.secondary for s in items):
        message = "보조 축 설정이 계열 설정과 맞지 않습니다"
        log.add(("chart", "secondary_axis"), "chart-secondary-mismatch", message)
        return None
    return tuple(items)
