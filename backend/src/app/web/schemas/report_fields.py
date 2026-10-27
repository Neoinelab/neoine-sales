"""Reports 필드 카탈로그 응답 스키마. 카탈로그 내용은 domain·application이 정한다."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.domain.report.labels import OperatorShape
from app.domain.report.vocabulary import (
    Aggregate,
    Entity,
    FieldType,
    Format,
    Operator,
    OptionsSource,
    RelativePeriod,
    ValueKind,
)

if TYPE_CHECKING:
    from app.application.report.views import ReportCatalogView


class _FromView(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReportLimitsResponse(_FromView):
    columns_min: int
    columns_max: int
    conditions_max: int
    row_limits: list[int]
    default_row_limit: int
    statement_timeout_seconds: int
    text_value_max: int
    list_value_max: int
    last_n_days_max: int
    label_max: int
    prefix_max: int


class ReportEntityResponse(_FromView):
    key: Entity
    label: str


class ReportFormatResponse(_FromView):
    key: Format
    label: str
    affects_query: bool


class ReportOperatorResponse(_FromView):
    key: Operator
    label: str
    value: OperatorShape


class ReportAggregateResponse(_FromView):
    key: Aggregate
    label: str


class ReportRelativePeriodResponse(_FromView):
    key: RelativePeriod
    label: str
    needs_days: bool


class ReportFieldOptionResponse(_FromView):
    value: str
    label: str


class ReportFieldResponse(_FromView):
    key: str
    label: str
    entity: Entity
    type: FieldType
    formats: list[Format]
    default_format: Format
    operators: list[Operator]
    aggregates: list[Aggregate]
    default_aggregate: Aggregate | None
    groupable: bool
    filterable: bool
    requires_grouping: bool
    deal_number: bool
    value_kind: ValueKind | None
    options: list[ReportFieldOptionResponse] | None
    options_source: OptionsSource | None
    options_category: str | None


class ReportCatalogResponse(_FromView):
    limits: ReportLimitsResponse
    entities: list[ReportEntityResponse]
    formats: list[ReportFormatResponse]
    operators: list[ReportOperatorResponse]
    aggregates: list[ReportAggregateResponse]
    relative_periods: list[ReportRelativePeriodResponse]
    fields: list[ReportFieldResponse]

    @classmethod
    def from_view(cls, view: ReportCatalogView) -> ReportCatalogResponse:
        return cls.model_validate(view)
