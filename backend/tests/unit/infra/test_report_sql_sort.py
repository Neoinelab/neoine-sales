"""Reports SQL 생성: 컬럼별 정렬이 ORDER BY가 되는 규칙.

정렬이 있는 컬럼만 컬럼 순서대로 ORDER BY에 들어가고, 그 뒤에 동률 처리 키가 붙는다.
"""

from tests.support.report_defs import col, resolved
from tests.support.report_sql import sql_of


def _order_by(sql: str) -> str:
    """ORDER BY 절만(LIMIT 앞까지)."""
    tail = sql[sql.index("ORDER BY") :]
    return tail.split("LIMIT")[0]


def _before(text: str, first: str, second: str) -> bool:
    return text.index(first) < text.index(second)


def test_plain_order_by_follows_sorted_columns_in_column_order() -> None:
    """정렬한 컬럼은 컬럼 순서대로 ORDER BY에 들어가고 Deal code 동률 키가 뒤에 붙는다.

    테스트 코드: RQ-051
    """
    # when: 이름 오름차순·Vendor 내림차순 SQL을 만든다
    sql = sql_of(resolved([col("deal.name", sort="asc"), col("deal.vendor", sort="desc")]))

    # then: 이름 ASC, Vendor DESC, deal_code ASC 순서이고 NULLS LAST다
    order = _order_by(sql)
    assert "deals.name ASC NULLS LAST" in order
    assert "v.name DESC NULLS LAST" in order
    assert _before(order, "deals.name ASC", "v.name DESC")
    assert _before(order, "v.name DESC", "deals.deal_code ASC")


def test_unsorted_column_is_not_in_order_by() -> None:
    """정렬하지 않은 컬럼은 ORDER BY에 없다.

    테스트 코드: RQ-051
    """
    # when: 이름만 정렬한 SQL을 만든다
    sql = sql_of(resolved([col("deal.name", sort="asc"), col("deal.vendor")]))

    # then: Vendor는 ORDER BY에 없고 이름 뒤에 deal_code가 온다
    order = _order_by(sql)
    assert "v.name" not in order
    assert _before(order, "deals.name ASC", "deals.deal_code ASC")


def test_report_without_column_sort_orders_by_deal_code_only() -> None:
    """컬럼 정렬이 없으면 Deal code 순으로만 정렬한다.

    테스트 코드: RQ-051
    """
    # when: 정렬 없는 SQL을 만든다
    sql = sql_of(resolved([col("deal.name"), col("deal.vendor")]))

    # then: ORDER BY에 deal_code ASC뿐이다
    order = _order_by(sql)
    assert "deals.name" not in order
    assert "v.name" not in order
    assert "deals.deal_code ASC" in order


def test_swapping_sorted_columns_swaps_order_by_priority() -> None:
    """정렬 컬럼의 순서를 바꾸면 ORDER BY 우선순위도 바뀐다.

    테스트 코드: RQ-051
    """
    # when: Vendor 내림차순을 먼저, 이름 오름차순을 나중에 둔 SQL을 만든다
    sql = sql_of(resolved([col("deal.vendor", sort="desc"), col("deal.name", sort="asc")]))

    # then: Vendor가 이름보다 먼저 정렬된다
    order = _order_by(sql)
    assert _before(order, "v.name DESC", "deals.name ASC")


def test_action_rows_keep_acted_on_and_id_tie_breakers_after_sort_keys() -> None:
    """Action 행은 정렬 키 뒤에 Deal code, 수행일 동률 키가 붙는다.

    테스트 코드: RQ-053
    """
    # when: 이름 내림차순과 Action 컬럼의 SQL을 만든다
    sql = sql_of(resolved([col("deal.name", sort="desc"), col("action.action")]))

    # then: 이름, deal_code, acted_on 순서다
    order = _order_by(sql)
    assert _before(order, "deals.name DESC", "deals.deal_code ASC")
    assert _before(order, "deals.deal_code ASC", "acted_on ASC")


def test_grouped_order_by_uses_sort_keys_then_remaining_groups() -> None:
    """그룹핑 리포트의 ORDER BY는 정렬 키 뒤에 남은 그룹 키가 온다.

    테스트 코드: RQ-052
    """
    # when: Status 그룹, Vendor 그룹(오름차순), 금액 합계(내림차순)의 SQL을 만든다
    sql = sql_of(
        resolved(
            [
                col("deal.status", group=True),
                col("deal.vendor", group=True, sort="asc"),
                col("deal.amount", aggregate="sum", sort="desc"),
            ]
        )
    )

    # then: Vendor 이름 식, 합계 열, Status 정렬 식·키, Vendor 키 순서다
    order = _order_by(sql)
    # Vendor 이름 식(i4) -> 합계 열(c2) -> 아직 안 쓴 Status 정렬 식(i2)·키(i0) -> Vendor 키(i3)
    assert "base.i4 ASC NULLS LAST" in order
    assert "c2 DESC NULLS LAST" in order
    assert _before(order, "base.i4", "c2 DESC")
    assert _before(order, "c2 DESC", "base.i2")
    assert _before(order, "base.i2", "base.i0")
    assert _before(order, "base.i0", "base.i3")


def test_grouped_sort_priority_follows_column_order() -> None:
    """그룹핑 리포트의 정렬 우선순위도 컬럼 순서를 따른다.

    테스트 코드: RQ-052
    """
    # when: 금액 합계(오름차순)를 첫 컬럼, Vendor 그룹(내림차순)을 둘째로 둔 SQL을 만든다
    sql = sql_of(
        resolved(
            [
                col("deal.amount", aggregate="sum", sort="asc"),
                col("deal.vendor", group=True, sort="desc"),
            ]
        )
    )

    # then: 합계 열 ASC, Vendor DESC, 남은 그룹 키 ASC의 세 키다
    keys = [part.strip() for part in _order_by(sql).removeprefix("ORDER BY").split(",")]
    # 집계 열(오름차순) -> Vendor 그룹 정렬 식(내림차순) -> 남은 그룹 키(오름차순)
    assert keys[0] == "c0 ASC NULLS LAST"
    assert keys[1].startswith("base.")
    assert keys[1].endswith("DESC NULLS LAST")
    assert keys[2].startswith("base.")
    assert keys[2].endswith("ASC NULLS LAST")
    assert len(keys) == 3


def test_grouped_report_with_only_aggregate_sort_still_ends_with_group_keys() -> None:
    """집계 열만 정렬해도 ORDER BY 끝에 그룹 키가 붙는다.

    테스트 코드: RQ-052
    """
    # when: Status 그룹과 금액 합계(내림차순)의 SQL을 만든다
    sql = sql_of(
        resolved([col("deal.status", group=True), col("deal.amount", aggregate="sum", sort="desc")])
    )

    # then: 합계 열 뒤에 Status 키들이 온다
    order = _order_by(sql)
    assert _before(order, "c1 DESC", "base.i2")
    assert "base.i0" in order
