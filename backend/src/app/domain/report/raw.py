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


@dataclass(frozen=True, slots=True)
class RawCondition:
    field: str
    operator: str
    value: object = None


@dataclass(frozen=True, slots=True)
class RawSort:
    column: object
    direction: object = "asc"


@dataclass(frozen=True, slots=True)
class RawReportDefinition:
    columns: tuple[RawColumn, ...]
    conditions: tuple[RawCondition, ...] = ()
    combine: object = "and"
    sort: RawSort | None = None
    row_limit: object = 1000
