"""저장용 정의 JSON: 원시 정의 <-> JSON, 정의가 쓰는 엔티티.

저장 형식은 `/query` 요청과 같은 모양(snake_case)이고, 검증을 통과한 원시 정의 그대로다.
"""

from typing import TYPE_CHECKING

from app.domain.report.catalog import find_field
from app.domain.report.errors import ReportDefinitionError, ReportIssue
from app.domain.report.raw import RawColumn, RawCondition, RawReportDefinition, RawSort
from app.domain.report.vocabulary import DEFAULT_ROW_LIMIT, Entity

if TYPE_CHECKING:
    from collections.abc import Mapping

BROKEN_DEFINITION = ReportIssue(
    ("definition",), "stored-invalid", "저장된 리포트 정의를 읽을 수 없습니다."
)


def definition_to_json(raw: RawReportDefinition) -> dict[str, object]:
    return {
        "columns": [
            {
                "field": c.field,
                "label": c.label,
                "format": c.format,
                "prefix_length": c.prefix_length,
                "group": c.group,
                "aggregate": c.aggregate,
            }
            for c in raw.columns
        ],
        "conditions": [
            {"field": c.field, "operator": c.operator, "value": c.value} for c in raw.conditions
        ],
        "combine": raw.combine,
        "sort": None
        if raw.sort is None
        else {"column": raw.sort.column, "direction": raw.sort.direction},
        "row_limit": raw.row_limit,
    }


def _items(data: Mapping[str, object], key: str, *, required: bool) -> list[Mapping[str, object]]:
    value = data.get(key, None if required else [])
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise ReportDefinitionError([BROKEN_DEFINITION])
    return value


def _text(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if type(value) is not str:
        raise ReportDefinitionError([BROKEN_DEFINITION])
    return value


def _optional_text(item: Mapping[str, object], key: str) -> str | None:
    value = item.get(key)
    if value is not None and type(value) is not str:
        raise ReportDefinitionError([BROKEN_DEFINITION])
    return value


_LEGACY_FORMATS = frozenset({"as_is", "prefix", "name", "key"})


def _column(item: Mapping[str, object]) -> RawColumn:
    group = item.get("group", False)
    if type(group) is not bool:
        raise ReportDefinitionError([BROKEN_DEFINITION])
    return RawColumn(
        field=_text(item, "field"),
        label=_optional_text(item, "label"),
        format=_current_format(_optional_text(item, "format")),
        prefix_length=item.get("prefix_length"),
        group=group,
        aggregate=_optional_text(item, "aggregate"),
    )


def _current_format(raw: str | None) -> str | None:
    """예전 포맷(그대로·앞 N자·이름·코드)은 포맷 없음으로 읽는다. 앞 N자의 N은 그대로 둔다."""
    return None if raw in _LEGACY_FORMATS else raw


def _sort(data: object) -> RawSort | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ReportDefinitionError([BROKEN_DEFINITION])
    return RawSort(column=data.get("column"), direction=data.get("direction", "asc"))


def definition_from_json(data: object) -> RawReportDefinition:
    """깨진 모양이면 ReportDefinitionError(stored-invalid). 값 검증은 실행 때 다시 한다."""
    if not isinstance(data, dict):
        raise ReportDefinitionError([BROKEN_DEFINITION])
    columns = tuple(_column(c) for c in _items(data, "columns", required=True))
    conditions = tuple(
        RawCondition(field=_text(c, "field"), operator=_text(c, "operator"), value=c.get("value"))
        for c in _items(data, "conditions", required=False)
    )
    return RawReportDefinition(
        columns=columns,
        conditions=conditions,
        combine=data.get("combine", "and"),
        sort=_sort(data.get("sort")),
        row_limit=data.get("row_limit", DEFAULT_ROW_LIMIT),
    )


def definition_entities(raw: RawReportDefinition) -> tuple[Entity, ...]:
    """컬럼·조건에 쓰인 필드의 엔티티. Deal은 항상 첫째, 모르는 key는 건너뛴다."""
    keys = [c.field for c in raw.columns] + [c.field for c in raw.conditions]
    used = {spec.entity for key in keys if (spec := find_field(key)) is not None}
    return (Entity.DEAL, *([Entity.ACTION] if Entity.ACTION in used else []))
