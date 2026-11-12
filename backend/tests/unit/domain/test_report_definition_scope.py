"""리포트 정의의 행 범위 판정.

Action 필드가 컬럼에 있는지 조건에만 있는지, Deal 숫자를 Deal당 한 번 계산하는지 본다.
"""

import pytest

from app.domain.report.definition import ActionFilter, RowScope
from tests.support.report_defs import col, cond, parse

VENDOR_GROUP = col("deal.vendor", group=True)
ACTION_TYPE = col("action.type", group=True)


def test_row_scope_is_action_when_an_action_column_exists() -> None:
    """Action 필드가 컬럼에 있으면 행 범위는 Action이고 Action과 JOIN한다.

    테스트 코드: RQ-028
    """
    # given: Deal 컬럼과 Action 컬럼이 있는 정의
    definition = parse([col("deal.code"), col("action.action")])

    # when: 행 범위와 Action 조건 방식을 구한다
    row_scope = definition.row_scope()
    action_filter = definition.action_filter()
    # then: 행 범위는 Action이고 Action 조건 방식은 JOIN이다
    assert row_scope == RowScope.ACTION
    assert action_filter == ActionFilter.JOIN


def test_action_only_in_conditions_gives_deal_scope_with_exists() -> None:
    """Action 필드가 조건에만 있으면 행 범위는 Deal이고 EXISTS로 거른다.

    테스트 코드: RQ-029
    """
    # given: Action 필드가 조건에만 있는 정의
    definition = parse([col("deal.code")], [cond("action.type", "in", [1])])

    # when: 행 범위와 Action 조건 방식을 구한다
    row_scope = definition.row_scope()
    action_filter = definition.action_filter()
    # then: 행 범위는 Deal이고 Action 조건 방식은 EXISTS다
    assert row_scope == RowScope.DEAL
    assert action_filter == ActionFilter.EXISTS


def test_no_action_field_gives_deal_scope_without_filter() -> None:
    """Action 필드가 전혀 없으면 행 범위는 Deal이고 Action 조건 방식이 없다.

    테스트 코드: RQ-031
    """
    # given: Deal 필드만 쓰는 정의
    definition = parse([col("deal.code")], [cond("deal.name", "contains", "a")])

    # when: 행 범위와 Action 조건 방식을 구한다
    row_scope = definition.row_scope()
    action_filter = definition.action_filter()
    # then: 행 범위는 Deal이고 Action 조건 방식은 NONE이다
    assert row_scope == RowScope.DEAL
    assert action_filter == ActionFilter.NONE


def test_action_column_wins_over_action_conditions() -> None:
    """Action 컬럼이 있으면 Action 조건이 있어도 JOIN이 우선한다.

    테스트 코드: RQ-028
    """
    # given: Action 컬럼과 Action 조건이 함께 있는 정의
    definition = parse([col("action.memo")], [cond("action.type", "in", [1])])

    # when: 행 범위와 Action 조건 방식을 구한다
    row_scope = definition.row_scope()
    action_filter = definition.action_filter()
    # then: 행 범위는 Action이고 조건 방식은 JOIN이다
    assert row_scope == RowScope.ACTION
    assert action_filter == ActionFilter.JOIN


def test_action_count_column_makes_action_scope() -> None:
    """Action 건수 컬럼도 행 범위를 Action으로 만든다.

    테스트 코드: RQ-020
    """
    # given: Vendor 그룹과 Action 건수 컬럼이 있는 정의
    definition = parse([VENDOR_GROUP, col("action.count")])

    # when: 행 범위와 Action 조건 방식을 구한다
    row_scope = definition.row_scope()
    action_filter = definition.action_filter()
    # then: 행 범위는 Action이고 조건 방식은 JOIN이다
    assert row_scope == RowScope.ACTION
    assert action_filter == ActionFilter.JOIN


def test_is_grouped_follows_the_group_flags() -> None:
    """그룹핑 여부는 그룹 컬럼이 있는지로 정해진다.

    테스트 코드: RQ-017
    """
    # when: 그룹 컬럼이 있는 정의와 없는 정의의 그룹핑 여부를 구한다
    with_group = parse([VENDOR_GROUP, col("deal.code", aggregate="count")]).is_grouped()
    without_group = parse([col("deal.code")]).is_grouped()
    # then: 그룹 컬럼이 있으면 그룹핑이고 없으면 아니다
    assert with_group is True
    assert without_group is False


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        ([ACTION_TYPE, col("deal.amount", aggregate="sum")], True),
        ([ACTION_TYPE, col("deal.amount", aggregate="avg")], True),
        ([ACTION_TYPE, col("deal.users")], True),
        ([ACTION_TYPE, col("deal.status_days")], True),
        ([ACTION_TYPE, col("deal.amount", aggregate="min")], False),
        ([ACTION_TYPE, col("deal.amount", aggregate="max")], False),
        ([ACTION_TYPE, col("deal.code", aggregate="count")], False),
        ([ACTION_TYPE, col("action.count")], False),
        ([VENDOR_GROUP, col("deal.amount", aggregate="sum")], False),
        ([col("deal.amount"), col("action.memo")], False),
    ],
    ids=[
        "sum",
        "avg",
        "users-default-sum",
        "status-days-default-avg",
        "min-only",
        "max-only",
        "count-only",
        "action-count-only",
        "deal-scope",
        "ungrouped",
    ],
)
def test_deal_numbers_once_only_for_grouped_action_scope_sum_or_avg(
    columns: list[dict[str, object]], expected: bool
) -> None:
    """Deal당 한 번 세는 것은 Action 행 범위 그룹핑의 합계·평균 Deal 숫자일 때뿐이다.

    테스트 코드: RQ-047
    """
    # when: 정의의 Deal당 한 번 규칙을 구한다 (전제: 컬럼 조합 매개변수)
    once = parse(columns).deal_numbers_once()
    # then: 기대값과 같다
    assert once is expected
