"""리포트 정의 검증의 컬럼 규칙 (AC4, AC7, Q3): 포맷·집계 허용표, 그룹핑 규칙, 기본 집계,
`action.count`의 특수 규칙."""

import pytest

from app.domain.report.vocabulary import Aggregate, Format
from tests.support.report_defs import col, cond, issues, parse

VENDOR_GROUP = col("deal.vendor", group=True)


def test_text_field_rejects_a_date_format() -> None:
    found = issues([col("deal.code", format="quarter")])

    assert found == [(("columns", 0, "format"), "format-not-allowed")]


def test_number_field_rejects_quarter_format() -> None:
    found = issues([col("deal.amount", format="quarter")])

    assert found == [(("columns", 0, "format"), "format-not-allowed")]


def test_date_field_rejects_ymd_hm_but_datetime_field_accepts_it() -> None:
    assert issues([col("deal.expected_close", format="ymd_hm")]) == [
        (("columns", 0, "format"), "format-not-allowed")
    ]
    assert parse([col("deal.created_at", format="ymd_hm")]).columns[0].format == Format.YMD_HM


def test_omitted_format_uses_the_field_default() -> None:
    columns = parse([col("deal.amount"), col("deal.vendor"), col("deal.created_at")]).columns

    assert [c.format for c in columns] == [Format.KRW_THOUSAND, Format.NAME, Format.YMD_HM]


# ---- 그룹핑과 집계 (Q3) ----


def test_grouped_report_requires_an_aggregate_for_a_non_number_column() -> None:
    found = issues([VENDOR_GROUP, col("deal.code")])

    assert found == [(("columns", 1, "aggregate"), "aggregate-required")]


def test_grouped_report_accepts_count_and_count_distinct_for_text() -> None:
    columns = parse(
        [
            VENDOR_GROUP,
            col("deal.code", aggregate="count"),
            col("deal.name", aggregate="count_distinct"),
        ]
    ).columns

    assert [c.aggregate for c in columns] == [None, Aggregate.COUNT, Aggregate.COUNT_DISTINCT]


def test_grouped_report_applies_default_number_aggregates() -> None:
    columns = parse([VENDOR_GROUP, col("deal.amount"), col("deal.status_days")]).columns

    assert columns[1].aggregate == Aggregate.SUM
    assert columns[2].aggregate == Aggregate.AVG


def test_users_defaults_to_sum_when_grouped() -> None:
    assert parse([VENDOR_GROUP, col("deal.users")]).columns[1].aggregate == Aggregate.SUM


@pytest.mark.parametrize("aggregate", ["sum", "avg", "min", "max"])
def test_number_column_accepts_the_four_numeric_aggregates(aggregate: str) -> None:
    columns = parse([VENDOR_GROUP, col("deal.amount", aggregate=aggregate)]).columns

    assert columns[1].aggregate == Aggregate(aggregate)


def test_number_column_rejects_count() -> None:
    found = issues([VENDOR_GROUP, col("deal.amount", aggregate="count")])

    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_text_column_rejects_sum_when_grouped() -> None:
    found = issues([VENDOR_GROUP, col("deal.name", aggregate="sum")])

    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_unknown_aggregate_name_is_rejected() -> None:
    found = issues([VENDOR_GROUP, col("deal.amount", aggregate="median")])

    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_aggregate_without_any_grouping_is_rejected() -> None:
    found = issues([col("deal.code", aggregate="count")])

    assert found == [(("columns", 0, "aggregate"), "aggregate-not-allowed")]


def test_group_column_with_aggregate_is_rejected() -> None:
    found = issues([col("deal.vendor", group=True, aggregate="count")])

    assert found == [(("columns", 0, "aggregate"), "aggregate-not-allowed")]


def test_ungrouped_report_leaves_aggregates_empty() -> None:
    columns = parse([col("deal.amount"), col("deal.code")]).columns

    assert [c.aggregate for c in columns] == [None, None]
    assert [c.group for c in columns] == [False, False]


def test_a_date_column_can_be_grouped_by_quarter() -> None:
    columns = parse([col("deal.expected_close", format="quarter", group=True)]).columns

    assert columns[0].group is True
    assert columns[0].format == Format.QUARTER


# ---- action.count ----


def test_action_count_without_grouping_is_rejected() -> None:
    assert issues([col("action.count")]) == [(("columns", 0), "grouping-required")]


def test_action_count_in_conditions_is_not_filterable() -> None:
    found = issues([VENDOR_GROUP, col("action.count")], [cond("action.count", "eq", 1)])

    assert found == [(("conditions", 0, "field"), "not-filterable")]


def test_action_count_cannot_be_a_group_column() -> None:
    found = issues([VENDOR_GROUP, col("action.count", group=True)])

    assert found == [(("columns", 1, "group"), "group-not-allowed")]


def test_action_count_accepts_only_count_as_aggregate() -> None:
    found = issues([VENDOR_GROUP, col("action.count", aggregate="sum")])

    assert found == [(("columns", 1, "aggregate"), "aggregate-not-allowed")]


def test_action_count_is_accepted_when_grouped_with_or_without_count() -> None:
    plain = parse([VENDOR_GROUP, col("action.count")]).columns[1]
    explicit = parse([VENDOR_GROUP, col("action.count", aggregate="count")]).columns[1]

    assert plain.aggregate == Aggregate.COUNT
    assert explicit.aggregate == Aggregate.COUNT
