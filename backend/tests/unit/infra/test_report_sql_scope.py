"""Reports SQL 생성: 행 범위(JOIN/EXISTS)와 필요한 조인만 추가 (AC1, AC5, AC8).

DB 없이 SQLAlchemy 문장을 컴파일한 문자열만 본다. 결과가 맞는지는 실제 DB 계약 테스트의 몫이다.
"""

from tests.support.report_defs import col, cond, resolved
from tests.support.report_sql import sql_of


def test_action_column_joins_deal_actions_without_exists() -> None:
    sql = sql_of(resolved([col("deal.code"), col("action.action")]))

    assert "JOIN deal_actions" in sql
    assert "EXISTS" not in sql


def test_action_condition_only_uses_exists_without_joining_actions() -> None:
    sql = sql_of(resolved([col("deal.code")], [cond("action.type", "in", [1])]))

    assert "EXISTS (SELECT" in sql
    assert "JOIN deal_actions" not in sql


def test_and_puts_all_action_conditions_in_one_exists() -> None:
    sql = sql_of(
        resolved(
            [col("deal.code")],
            [cond("action.type", "in", [1]), cond("action.next_action", "contains", "a")],
            combine="and",
        )
    )

    assert sql.count("EXISTS") == 1


def test_or_combines_action_conditions_inside_one_exists() -> None:
    sql = sql_of(
        resolved(
            [col("deal.code")],
            [
                cond("deal.name", "contains", "a"),
                cond("action.type", "in", [1]),
                cond("action.next_action", "contains", "a"),
            ],
            combine="or",
        )
    )

    assert sql.count("EXISTS") == 1
    assert " OR " in sql


def test_no_action_field_means_no_deal_actions_table_at_all() -> None:
    sql = sql_of(resolved([col("deal.code")], [cond("deal.name", "contains", "a")]))

    assert "deal_actions" not in sql


def test_only_needed_name_joins_are_added() -> None:
    sql = sql_of(resolved([col("deal.code")]))

    for table in ("JOIN users", "JOIN vendors", "JOIN codes", "JOIN contacts"):
        assert table not in sql


def test_vendor_column_adds_the_vendors_join_exactly_once() -> None:
    sql = sql_of(
        resolved(
            [col("deal.vendor", sort="asc")],
            [cond("deal.vendor", "in", [1])],
        )
    )

    assert sql.count("JOIN vendors") == 1


def test_owner_column_adds_the_users_join_once() -> None:
    sql = sql_of(resolved([col("deal.owner"), col("deal.code")]))

    assert sql.count("JOIN users") == 1
