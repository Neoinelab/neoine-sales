from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from app.application.ports.report_query_runner import ReportCell
    from app.domain.report.definition import ActionFilter, ReportColumn, RowScope
    from app.domain.report.fields import FieldSpec
    from app.domain.report.labels import OperatorShape
    from app.domain.report.vocabulary import (
        Aggregate,
        Entity,
        FieldType,
        Format,
        Operator,
        RelativePeriod,
        ResultValueType,
    )


@dataclass(frozen=True, slots=True)
class ReportLimits:
    columns_min: int
    columns_max: int
    conditions_max: int
    row_limits: tuple[int, ...]
    default_row_limit: int
    statement_timeout_seconds: int
    text_value_max: int
    list_value_max: int
    last_n_days_max: int
    label_max: int
    prefix_max: int


@dataclass(frozen=True, slots=True)
class EntityInfo:
    key: Entity
    label: str


@dataclass(frozen=True, slots=True)
class FormatInfo:
    key: Format
    label: str
    affects_query: bool


@dataclass(frozen=True, slots=True)
class OperatorInfo:
    key: Operator
    label: str
    value: OperatorShape


@dataclass(frozen=True, slots=True)
class AggregateInfo:
    key: Aggregate
    label: str


@dataclass(frozen=True, slots=True)
class RelativePeriodInfo:
    key: RelativePeriod
    label: str
    needs_days: bool


@dataclass(frozen=True, slots=True)
class ReportCatalogView:
    limits: ReportLimits
    entities: tuple[EntityInfo, ...]
    formats: tuple[FormatInfo, ...]
    operators: tuple[OperatorInfo, ...]
    aggregates: tuple[AggregateInfo, ...]
    relative_periods: tuple[RelativePeriodInfo, ...]
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True, slots=True)
class ReportColumnView:
    index: int
    field: str
    label: str
    entity: Entity
    type: FieldType
    value_type: ResultValueType
    format: Format
    prefix_length: int | None
    group: bool
    aggregate: Aggregate | None

    @classmethod
    def of(cls, index: int, column: ReportColumn) -> ReportColumnView:
        return cls(
            index=index,
            field=column.field.key,
            label=column.label,
            entity=column.field.entity,
            type=column.field.type,
            value_type=column.value_type(),
            format=column.format,
            prefix_length=column.prefix_length,
            group=column.group,
            aggregate=column.aggregate,
        )


@dataclass(frozen=True, slots=True)
class ReportResultView:
    row_scope: RowScope
    action_filter: ActionFilter
    deal_numbers_once: bool
    columns: tuple[ReportColumnView, ...]
    rows: tuple[tuple[ReportCell, ...], ...]
    totals: tuple[ReportCell, ...] | None
    total_count: int
    truncated: bool
    row_limit: int
    sql: str
    elapsed_ms: int
    today: date
