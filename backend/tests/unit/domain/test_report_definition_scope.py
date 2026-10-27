"""리포트 정의의 행 범위 판정 (AC5, AC6, Q2, Q5): Action 필드가 컬럼에 있는지 조건에만 있는지,
Deal 숫자를 Deal당 한 번 계산하는지."""

import pytest

from app.domain.report.definition import ActionFilter, RowScope
from tests.support.report_defs import col, cond, parse

VENDOR_GROUP = col("deal.vendor", group=True)
ACTION_TYPE = col("action.type", group=True)


def test_row_scope_is_action_when_an_action_column_exists() -> None:
    definition = parse([col("deal.code"), col("action.action")])

    assert definition.row_scope() == RowScope.ACTION
    assert definition.action_filter() == ActionFilter.JOIN


def test_action_only_in_conditions_gives_deal_scope_with_exists() -> None:
    definition = parse([col("deal.code")], [cond("action.type", "in", [1])])

    assert definition.row_scope() == RowScope.DEAL
    assert definition.action_filter() == ActionFilter.EXISTS


def test_no_action_field_gives_deal_scope_without_filter() -> None:
    definition = parse([col("deal.code")], [cond("deal.name", "contains", "a")])

    assert definition.row_scope() == RowScope.DEAL
    assert definition.action_filter() == ActionFilter.NONE


def test_action_column_wins_over_action_conditions() -> None:
    definition = parse([col("action.memo")], [cond("action.type", "in", [1])])

    assert definition.row_scope() == RowScope.ACTION
    assert definition.action_filter() == ActionFilter.JOIN


def test_action_count_column_makes_action_scope() -> None:
    definition = parse([VENDOR_GROUP, col("action.count")])

    assert definition.row_scope() == RowScope.ACTION
    assert definition.action_filter() == ActionFilter.JOIN


def test_is_grouped_follows_the_group_flags() -> None:
    assert parse([VENDOR_GROUP, col("deal.code", aggregate="count")]).is_grouped() is True
    assert parse([col("deal.code")]).is_grouped() is False


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
    assert parse(columns).deal_numbers_once() is expected
