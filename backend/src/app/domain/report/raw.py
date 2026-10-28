"""웹이 넘기는 원시 리포트 정의. 값은 JSON에서 온 그대로이며 허용 여부는 도메인이 판단한다."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawColumn:
    field: str
    label: str | None = None
    format: str | None = None
    prefix_length: object = None
    group: bool = False
    aggregate: str | None = None
    sort: str | None = None


@dataclass(frozen=True, slots=True)
class RawCondition:
    field: str
    operator: str
    value: object = None


@dataclass(frozen=True, slots=True)
class RawReportDefinition:
    columns: tuple[RawColumn, ...]
    conditions: tuple[RawCondition, ...] = ()
    combine: object = "and"
    row_limit: object = 1000


@dataclass(frozen=True, slots=True)
class RawChart:
    """웹이 넘기는 원시 차트 설정. 값은 JSON에서 온 그대로이며 허용 여부는 도메인이 판단한다."""

    kind: object
    category: object
    values: object
    series: object = None
    swap: object = False
    title: object = ""
    legend: object = "top"
    data_labels: object = False
    category_axis_title: object = ""
    value_axis_title: object = ""
    value_min: object = None
    value_max: object = None
    secondary_axis: object = False
