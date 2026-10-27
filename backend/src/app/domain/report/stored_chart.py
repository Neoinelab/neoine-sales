"""저장용 차트 JSON: 원시 차트 <-> JSON. 읽을 때는 모양과 값의 형식만 확인한다."""

from typing import TYPE_CHECKING

from app.domain.report.chart import ChartKind, LegendPosition
from app.domain.report.errors import ReportDefinitionError, ReportIssue
from app.domain.report.raw import RawChart

if TYPE_CHECKING:
    from collections.abc import Mapping

BROKEN_CHART = ReportIssue(("chart",), "stored-invalid", "저장된 차트 설정을 읽을 수 없습니다.")

_TEXT_KEYS = ("title", "category_axis_title", "value_axis_title")
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
        and _is_int(data.get("category"))
        and isinstance(values, list)
        and all(_is_int(v) for v in values)
    )
    if not valid:
        raise _broken()


def _check_optional(data: Mapping[str, object]) -> None:
    series = data.get("series")
    valid = (
        (series is None or _is_int(series))
        and all(type(data.get(k, "")) is str for k in _TEXT_KEYS)
        and all(type(data.get(k, False)) is bool for k in _FLAG_KEYS)
        and all(data.get(k) is None or _is_number(data.get(k)) for k in ("value_min", "value_max"))
    )
    if not valid:
        raise _broken()


def chart_from_json(data: object) -> RawChart:
    """깨진 모양이면 ReportDefinitionError(stored-invalid). 정의 기준 검사는 하지 않는다."""
    if not isinstance(data, dict) or not all(k in data for k in ("kind", "category", "values")):
        raise _broken()
    _check_required(data)
    _check_optional(data)
    return RawChart(
        kind=data["kind"],
        category=data["category"],
        values=list(data["values"]),
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
    )
