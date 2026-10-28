"""Reports SQL 생성: 그룹핑·Q5(Deal당 한 번)·날짜 묶음·정렬·행 수·합계 문장 (AC6, AC9, AC13)."""

import pytest

from tests.support.report_defs import col, cond, resolved
from tests.support.report_sql import build, compiled, sql_of

ACTION_TYPE = col("action.type", group=True)


def test_grouped_action_scope_sums_deal_numbers_once() -> None:
    sql = sql_of(resolved([ACTION_TYPE, col("deal.amount", aggregate="sum")]))

    assert "row_number() OVER (PARTITION BY" in sql
    assert "CASE WHEN" in sql


def test_grouped_action_scope_averages_deal_numbers_once() -> None:
    sql = sql_of(resolved([ACTION_TYPE, col("deal.users", aggregate="avg")]))

    assert "CASE WHEN" in sql


def test_min_and_max_of_deal_numbers_need_no_once_per_deal_case() -> None:
    sql = sql_of(
        resolved(
            [
                ACTION_TYPE,
                col("deal.amount", aggregate="min"),
                col("deal.users", aggregate="max"),
            ]
        )
    )

    assert "CASE WHEN" not in sql


def test_deal_scope_grouping_does_not_need_the_once_per_deal_case() -> None:
    sql = sql_of(resolved([col("deal.vendor", group=True), col("deal.amount")]))

    assert "CASE WHEN" not in sql


def test_date_quarter_format_changes_select_and_group_by() -> None:
    sql = sql_of(
        resolved([col("deal.expected_close", format="quarter", group=True), col("deal.amount")])
    )

    assert "to_char" in sql
    assert "GROUP BY" in sql


def test_datetime_year_format_converts_to_the_business_timezone() -> None:
    sql = sql_of(resolved([col("deal.created_at", format="year", group=True), col("deal.amount")]))

    assert "timezone(" in sql
    assert "GROUP BY" in sql


def test_display_only_format_does_not_change_the_statement() -> None:
    plain = sql_of(resolved([col("deal.expected_close", format="ymd"), col("deal.code")]))
    weekday = sql_of(resolved([col("deal.expected_close", format="weekday"), col("deal.code")]))

    assert plain == weekday


def test_nulls_last_and_tie_breakers_are_appended() -> None:
    sql = sql_of(
        resolved(
            [col("deal.name", sort="desc"), col("deal.code")],
        )
    )

    assert "NULLS LAST" in sql
    assert "deal_code ASC" in sql


def test_action_rows_are_tie_broken_by_acted_at_and_id() -> None:
    sql = sql_of(resolved([col("deal.code"), col("action.action")]))

    assert "acted_at ASC" in sql
    assert "deal_actions.id ASC" in sql or "a.id ASC" in sql


def test_total_count_comes_from_the_same_statement_and_rows_are_limited() -> None:
    sql = sql_of(resolved([col("deal.code")], row_limit=100))

    assert "count(*) OVER ()" in sql
    assert "LIMIT" in sql


def test_grouped_report_orders_by_group_columns_without_explicit_sort() -> None:
    sql = sql_of(resolved([col("deal.status", group=True), col("deal.code", aggregate="count")]))

    assert "ORDER BY" in sql
    assert "sort_order" in sql  # Status는 codes.sort_order 순서


def test_totals_statement_exists_only_for_grouped_reports() -> None:
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    grouped = resolved([col("deal.vendor", group=True), col("deal.amount")])
    plain = resolved([col("deal.vendor"), col("deal.amount")])

    assert build_totals_select(plain) is None
    assert build_totals_select(grouped) is not None


def test_totals_statement_has_no_group_by_and_no_row_limit() -> None:
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved(
        [col("deal.vendor", group=True), col("deal.amount")],
        [cond("deal.amount", "gt", 5)],
    )
    statement = build_totals_select(report)

    assert statement is not None
    sql, _ = compiled(statement)
    assert "GROUP BY" not in sql
    assert "LIMIT" not in sql
    assert "sum(" in sql.lower()


def test_totals_statement_for_action_scope_keeps_the_once_per_deal_case() -> None:
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved([ACTION_TYPE, col("deal.amount", aggregate="sum")])
    statement = build_totals_select(report)

    assert statement is not None
    assert "CASE WHEN" in compiled(statement)[0]


@pytest.mark.parametrize("limit", [100, 1000, 10000])
def test_each_row_limit_builds_a_statement(limit: int) -> None:
    assert build(resolved([col("deal.code")], row_limit=limit)) is not None


def test_totals_statement_counts_distinct_over_the_whole_range() -> None:
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved(
        [col("deal.vendor", group=True), col("deal.owner", aggregate="count_distinct")]
    )
    statement = build_totals_select(report)

    assert statement is not None
    sql = compiled(statement)[0]
    assert "count(DISTINCT" in sql
    assert "GROUP BY" not in sql


def test_totals_statement_is_none_when_no_measure_column_exists() -> None:
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved([col("deal.forecast", group=True), col("deal.vendor", group=True)])

    assert build_totals_select(report) is None


# ---- 앞 N자는 SQL에 쓰지 않는다 / 코드 컬럼 값은 이름 식 (2026-10-28) ----


def test_prefix_length_does_not_change_sql() -> None:
    plain = sql_of(resolved([col("deal.name", group=True), col("deal.amount")]))
    prefixed = sql_of(resolved([col("deal.name", group=True, prefix_length=3), col("deal.amount")]))

    assert plain == prefixed


def test_prefix_length_does_not_change_sql_for_aggregate_and_date_columns() -> None:
    columns = [col("deal.expected_close", format="quarter", group=True), col("deal.amount")]
    prefixed = [
        col("deal.expected_close", format="quarter", group=True, prefix_length=2),
        col("deal.amount", prefix_length=4),
    ]

    assert sql_of(resolved(columns)) == sql_of(resolved(prefixed))


def test_code_column_value_is_name_expression() -> None:
    sql = sql_of(resolved([col("deal.status", group=True), col("deal.amount")]))

    assert "cs.name AS" in sql
    assert sql.startswith("SELECT base.i1 AS c0")  # 첫 컬럼의 값은 key(i0)가 아니라 이름(i1)
