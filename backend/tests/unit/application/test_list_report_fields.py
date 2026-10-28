"""ListReportFields (AC1): 필드 카탈로그와 한도를 DB·시계 없이 돌려준다."""

from app.application.report.list_fields import ListReportFields
from app.domain.report.catalog import FIELD_CATALOG
from app.domain.report.vocabulary import FieldType, Format


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


def test_catalog_fields_without_formats_have_null_default() -> None:
    fields = ListReportFields().execute().fields
    formatless = [f for f in fields if f.type in {FieldType.TEXT, FieldType.CODE, FieldType.USER}]

    assert formatless
    assert all(tuple(f.formats) == () and f.default_format is None for f in formatless)
    amount = next(f for f in fields if f.key == "deal.amount")
    assert amount.default_format == Format.KRW_THOUSAND


def test_catalog_formats_are_twelve_and_query_affecting_ones_are_date_buckets() -> None:
    view = ListReportFields().execute()

    assert len(view.formats) == 12
    assert {f.key.value for f in view.formats if f.affects_query} == {
        "ymd",
        "year",
        "quarter",
        "month",
    }
    assert not {"as_is", "prefix", "name", "key"} & {f.key.value for f in view.formats}
    assert view.limits.prefix_max == 200
