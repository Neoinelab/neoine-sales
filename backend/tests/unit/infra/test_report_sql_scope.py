"""Reports SQL 생성: 행 범위(JOIN/EXISTS)와 필요한 조인만 추가.

DB 없이 SQLAlchemy 문장을 컴파일한 문자열만 본다. 결과가 맞는지는 실제 DB 계약 테스트의 몫이다.
"""

from tests.support.report_defs import col, cond, resolved
from tests.support.report_sql import sql_of


def test_action_column_joins_deal_actions_without_exists() -> None:
    """Action 컬럼이 있으면 deal_actions를 JOIN하고 EXISTS는 쓰지 않는다.

    테스트 코드: RQ-028
    """
    # when: Action 컬럼이 있는 SQL을 만든다
    sql = sql_of(resolved([col("deal.code"), col("action.action")]))

    # then: JOIN이 있고 EXISTS가 없다
    assert "JOIN deal_actions" in sql
    assert "EXISTS" not in sql


def test_action_condition_only_uses_exists_without_joining_actions() -> None:
    """Action 필드가 조건에만 있으면 EXISTS로 거르고 JOIN하지 않는다.

    테스트 코드: RQ-029
    """
    # when: Action 조건만 있는 SQL을 만든다
    sql = sql_of(resolved([col("deal.code")], [cond("action.type", "in", [1])]))

    # then: EXISTS가 있고 JOIN이 없다
    assert "EXISTS (SELECT" in sql
    assert "JOIN deal_actions" not in sql


def test_and_puts_all_action_conditions_in_one_exists() -> None:
    """AND면 모든 Action 조건이 하나의 EXISTS 안에 들어간다.

    테스트 코드: RQ-030
    """
    # when: Action 조건 둘을 AND로 묶은 SQL을 만든다
    sql = sql_of(
        resolved(
            [col("deal.code")],
            [cond("action.type", "in", [1]), cond("action.next_action", "contains", "a")],
            combine="and",
        )
    )

    # then: EXISTS가 하나다
    assert sql.count("EXISTS") == 1


def test_or_combines_action_conditions_inside_one_exists() -> None:
    """OR면 Action 조건들이 하나의 EXISTS 안에서 OR로 묶인다.

    테스트 코드: RQ-030
    """
    # when: Deal 조건 하나와 Action 조건 둘을 OR로 묶은 SQL을 만든다
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

    # then: EXISTS가 하나이고 OR이 있다
    assert sql.count("EXISTS") == 1
    assert " OR " in sql


def test_no_action_field_means_no_deal_actions_table_at_all() -> None:
    """Action 필드가 없으면 deal_actions를 전혀 쓰지 않는다.

    테스트 코드: RQ-031
    """
    # when: Deal 필드만 쓰는 SQL을 만든다
    sql = sql_of(resolved([col("deal.code")], [cond("deal.name", "contains", "a")]))

    # then: deal_actions가 SQL에 없다
    assert "deal_actions" not in sql


def test_only_needed_name_joins_are_added() -> None:
    """컬럼이 필요로 하지 않는 이름 JOIN은 붙지 않는다.

    테스트 코드: RQ-060
    """
    # when: Deal code만 보는 SQL을 만든다
    sql = sql_of(resolved([col("deal.code")]))

    # then: users·vendors·codes·contacts JOIN이 모두 없다
    for table in ("JOIN users", "JOIN vendors", "JOIN codes", "JOIN contacts"):
        assert table not in sql


def test_vendor_column_adds_the_vendors_join_exactly_once() -> None:
    """Vendor를 컬럼과 조건에 함께 써도 vendors JOIN은 한 번이다.

    테스트 코드: RQ-060
    """
    # when: Vendor 컬럼(정렬)과 Vendor 조건이 있는 SQL을 만든다
    sql = sql_of(
        resolved(
            [col("deal.vendor", sort="asc")],
            [cond("deal.vendor", "in", [1])],
        )
    )

    # then: vendors JOIN이 한 번이다
    assert sql.count("JOIN vendors") == 1


def test_owner_column_adds_the_users_join_once() -> None:
    """담당자 컬럼은 users JOIN을 한 번만 붙인다.

    테스트 코드: RQ-060
    """
    # when: 담당자 컬럼의 SQL을 만든다
    sql = sql_of(resolved([col("deal.owner"), col("deal.code")]))

    # then: users JOIN이 한 번이다
    assert sql.count("JOIN users") == 1
