"""저장용 차트 JSON: 원시 차트 <-> JSON. 읽을 때는 모양과 값의 형식만 확인한다."""

from typing import TYPE_CHECKING

from app.domain.report.chart import (
    HISTOGRAM_BIN_KEYS,
    BinMode,
    ComboSeriesType,
    LegendPosition,
    auto_bins_json,
    legacy_combo_series_json,
)
from app.domain.report.chart_kinds import ChartKind
from app.domain.report.errors import ReportDefinitionError, ReportIssue
from app.domain.report.raw import RawChart

if TYPE_CHECKING:
    from collections.abc import Mapping

BROKEN_CHART = ReportIssue(("chart",), "stored-invalid", "저장된 차트 설정을 읽을 수 없습니다.")

_TEXT_KEYS = ("title", "category_axis_title", "value_axis_title")
_BIN_NUMBER_KEYS = ("bin_width", "overflow", "underflow")
_FLAG_KEYS = ("swap", "data_labels", "secondary_axis")


def chart_to_json(raw: RawChart) -> dict[str, object]:
    return {
        "kind": raw.kind,
        "category": raw.category,
        "series": raw.series,
        "values": raw.values,
        "swap": raw.swap,
        "title": raw.title,
        "legend": raw.legend,
        "data_labels": raw.data_labels,
        "category_axis_title": raw.category_axis_title,
        "value_axis_title": raw.value_axis_title,
        "value_min": raw.value_min,
        "value_max": raw.value_max,
        "secondary_axis": raw.secondary_axis,
        "histogram": raw.histogram,
        "show_total": raw.show_total,
        "combo_series": raw.combo_series,
    }


def _broken() -> ReportDefinitionError:
    return ReportDefinitionError([BROKEN_CHART])


def _is_int(value: object) -> bool:
    return type(value) is int


def _is_number(value: object) -> bool:
    return type(value) in {int, float}


def _check_required(data: Mapping[str, object]) -> None:
    kind, legend = data.get("kind"), data.get("legend", "top")
    values = data.get("values")
    valid = (
        type(kind) is str
        and kind in set(ChartKind)
        and type(legend) is str
        and legend in set(LegendPosition)
        and (data.get("category") is None or _is_int(data.get("category")))
        and isinstance(values, list)
        and all(_is_int(v) for v in values)
    )
    if not valid:
        raise _broken()


def _histogram_shape_ok(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict) or set(value) != HISTOGRAM_BIN_KEYS:
        return False
    count = value["bin_count"]
    return (
        type(value["bin_mode"]) is str
        and value["bin_mode"] in set(BinMode)
        and (count is None or _is_int(count))
        and all(value[k] is None or _is_number(value[k]) for k in _BIN_NUMBER_KEYS)
    )


def _combo_shape_ok(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, list) and all(
        isinstance(item, dict)
        and set(item) == {"type", "secondary"}
        and type(item["type"]) is str
        and item["type"] in set(ComboSeriesType)
        and type(item["secondary"]) is bool
        for item in value
    )


def _check_optional(data: Mapping[str, object]) -> None:
    series = data.get("series")
    valid = (
        (series is None or _is_int(series))
        and all(type(data.get(k, "")) is str for k in _TEXT_KEYS)
        and all(type(data.get(k, False)) is bool for k in _FLAG_KEYS)
        and all(data.get(k) is None or _is_number(data.get(k)) for k in ("value_min", "value_max"))
        and type(data.get("show_total", False)) is bool
        and _histogram_shape_ok(data.get("histogram"))
        and _combo_shape_ok(data.get("combo_series"))
    )
    if not valid:
        raise _broken()


def chart_from_json(data: object) -> RawChart:
    """깨진 모양이면 ReportDefinitionError(stored-invalid). 정의 기준 검사는 하지 않는다."""
    if not isinstance(data, dict) or not all(k in data for k in ("kind", "category", "values")):
        raise _broken()
    _check_required(data)
    _check_optional(data)
    kind, values = data["kind"], list(data["values"])
    histogram, combo = data.get("histogram"), data.get("combo_series")
    if kind == ChartKind.HISTOGRAM and histogram is None:
        histogram = auto_bins_json()
    if kind == ChartKind.COMBO and combo is None:
        combo = legacy_combo_series_json(len(values), secondary=data.get("secondary_axis") is True)
    return RawChart(
        kind=kind,
        category=data["category"],
        values=values,
        series=data.get("series"),
        swap=data.get("swap", False),
        title=data.get("title", ""),
        legend=data.get("legend", "top"),
        data_labels=data.get("data_labels", False),
        category_axis_title=data.get("category_axis_title", ""),
        value_axis_title=data.get("value_axis_title", ""),
        value_min=data.get("value_min"),
        value_max=data.get("value_max"),
        secondary_axis=data.get("secondary_axis", False),
        histogram=histogram,
        show_total=data.get("show_total", False),
        combo_series=combo,
    )
