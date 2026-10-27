"""ListReportFields (AC1): 필드 카탈로그와 한도를 DB·시계 없이 돌려준다."""

from app.application.report.list_fields import ListReportFields
from app.domain.report.catalog import FIELD_CATALOG


def test_list_report_fields_returns_the_whole_catalog() -> None:
    view = ListReportFields().execute()

    assert [f.key for f in view.fields] == [f.key for f in FIELD_CATALOG]


def test_list_report_fields_returns_the_limits_of_the_design() -> None:
    limits = ListReportFields().execute().limits

    assert limits.columns_min == 1
    assert limits.columns_max == 30
    assert limits.conditions_max == 20
    assert tuple(limits.row_limits) == (100, 1000, 10000)
    assert limits.default_row_limit == 1000
    assert limits.statement_timeout_seconds == 10
    assert limits.text_value_max == 200
    assert limits.list_value_max == 100
    assert limits.last_n_days_max == 3650
    assert limits.label_max == 100
    assert limits.prefix_max == 200
