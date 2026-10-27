from app.application.report.views import (
    AggregateInfo,
    EntityInfo,
    FormatInfo,
    OperatorInfo,
    RelativePeriodInfo,
    ReportCatalogView,
    ReportLimits,
)
from app.domain.report import vocabulary as v
from app.domain.report.catalog import FIELD_CATALOG
from app.domain.report.labels import (
    AGGREGATE_LABELS,
    ENTITY_LABELS,
    FORMAT_LABELS,
    OPERATOR_LABELS,
    PERIOD_LABELS,
)

_LIMITS = ReportLimits(
    columns_min=v.COLUMNS_MIN,
    columns_max=v.COLUMNS_MAX,
    conditions_max=v.CONDITIONS_MAX,
    row_limits=v.ROW_LIMITS,
    default_row_limit=v.DEFAULT_ROW_LIMIT,
    statement_timeout_seconds=v.STATEMENT_TIMEOUT_SECONDS,
    text_value_max=v.TEXT_VALUE_MAX,
    list_value_max=v.LIST_VALUE_MAX,
    last_n_days_max=v.LAST_N_DAYS_MAX,
    label_max=v.LABEL_MAX,
    prefix_max=v.PREFIX_MAX,
)


class ListReportFields:
    """리포트에 쓸 수 있는 필드 카탈로그와 한도. DB·시계가 필요 없다."""

    def execute(self) -> ReportCatalogView:
        return ReportCatalogView(
            limits=_LIMITS,
            entities=tuple(EntityInfo(key, label) for key, label in ENTITY_LABELS.items()),
            formats=tuple(
                FormatInfo(key, label, key.affects_query) for key, label in FORMAT_LABELS.items()
            ),
            operators=tuple(
                OperatorInfo(key, label, shape) for key, (label, shape) in OPERATOR_LABELS.items()
            ),
            aggregates=tuple(AggregateInfo(key, label) for key, label in AGGREGATE_LABELS.items()),
            relative_periods=tuple(
                RelativePeriodInfo(key, label, key is v.RelativePeriod.LAST_N_DAYS)
                for key, label in PERIOD_LABELS.items()
            ),
            fields=FIELD_CATALOG,
        )
