"""ReportQueryRunner(SQL) 계약: 행 범위(Action 행/Deal 행)와 Q5·Q-A (AC5, AC6, AC8)."""

from typing import TYPE_CHECKING

from tests.support.report_defs import col, cond
from tests.unit.repositories.report_case import kst

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

ONE_HUNDRED_MILLION = 100_000_000


async def test_action_column_gives_one_row_per_action_and_drops_deals_without_actions(
    report_case: ReportCase,
) -> None:
    with_actions = await report_case.add_deal(name="A")
    await report_case.add_deal(name="B")
    for hour, text in ((9, "a1"), (10, "a2"), (11, "a3")):
        await report_case.deals.add_action(with_actions, kst(2026, 10, 5, hour), action=text)

    rows = await report_case.rows([col("deal.name"), col("action.action")])

    assert rows == [("A", "a1"), ("A", "a2"), ("A", "a3")]


async def test_action_condition_only_keeps_one_row_per_matching_deal(
    report_case: ReportCase,
) -> None:
    meeting = await report_case.type_id("미팅")
    first = await report_case.add_deal(name="A")
    second = await report_case.add_deal(name="B")
    await report_case.add_deal(name="C")
    await report_case.deals.add_action(first, kst(2026, 10, 5), action_type="미팅")
    await report_case.deals.add_action(first, kst(2026, 10, 6), action_type="미팅")
    await report_case.deals.add_action(second, kst(2026, 10, 7), action_type="통화")

    result = await report_case.run([col("deal.name")], [cond("action.type", "in", [meeting])])

    assert [tuple(r) for r in result.rows] == [("A",)]
    assert result.total_count == 1


async def test_and_requires_one_action_to_meet_all_action_conditions(
    report_case: ReportCase,
) -> None:
    meeting = await report_case.type_id("미팅")
    deal = await report_case.add_deal(name="A")
    await report_case.deals.add_action(deal, kst(2026, 9, 10), action_type="미팅")
    await report_case.deals.add_action(deal, kst(2026, 10, 15), action_type="통화")
    conditions = [
        cond("action.type", "in", [meeting]),
        cond("action.acted_at", "relative", {"period": "this_month"}),
    ]

    anded = await report_case.rows([col("deal.name")], conditions, combine="and")
    ored = await report_case.rows([col("deal.name")], conditions, combine="or")

    assert anded == []  # 미팅은 9월, 이번 달 Action은 통화라서 한 Action이 둘 다 맞지 않는다
    assert ored == [("A",)]


async def test_or_mixes_deal_conditions_with_the_exists_of_action_conditions(
    report_case: ReportCase,
) -> None:
    meeting = await report_case.type_id("미팅")
    await report_case.add_deal(name="Match")
    by_action = await report_case.add_deal(name="Other")
    await report_case.add_deal(name="Neither")
    await report_case.deals.add_action(by_action, kst(2026, 10, 5), action_type="미팅")

    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.name", "equals", "match"), cond("action.type", "in", [meeting])],
        combine="or",
    )

    assert rows == [("Match",), ("Other",)]


async def test_and_combines_a_deal_condition_with_the_action_exists(
    report_case: ReportCase,
) -> None:
    meeting = await report_case.type_id("미팅")
    keep = await report_case.add_deal(name="Keep")
    drop = await report_case.add_deal(name="Drop")
    await report_case.deals.add_action(keep, kst(2026, 10, 5), action_type="미팅")
    await report_case.deals.add_action(drop, kst(2026, 10, 5), action_type="미팅")

    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.name", "equals", "keep"), cond("action.type", "in", [meeting])],
    )

    assert rows == [("Keep",)]


async def test_no_conditions_returns_every_deal(report_case: ReportCase) -> None:
    await report_case.add_deal(name="A")
    await report_case.add_deal(name="B")

    rows = await report_case.rows([col("deal.name")])

    assert rows == [("A",), ("B",)]


async def test_deal_amount_is_summed_once_per_deal_in_action_rows(
    report_case: ReportCase,
) -> None:
    first = await report_case.add_deal(amount=ONE_HUNDRED_MILLION)
    second = await report_case.add_deal(amount=3 * ONE_HUNDRED_MILLION)
    for hour in (9, 10, 11):
        await report_case.deals.add_action(first, kst(2026, 10, 5, hour))
    for hour in (9, 10):
        await report_case.deals.add_action(second, kst(2026, 10, 6, hour))

    rows = await report_case.rows(
        [
            col("deal.owner", group=True),
            col("deal.amount", aggregate="sum"),
            col("deal.amount", aggregate="avg"),
            col("deal.amount", aggregate="min"),
            col("deal.amount", aggregate="max"),
            col("action.count"),
        ]
    )

    assert rows == [
        ("owner", 4 * ONE_HUNDRED_MILLION, 2 * ONE_HUNDRED_MILLION, 100_000_000, 300_000_000, 5)
    ]


async def test_deal_users_and_status_days_follow_the_once_per_deal_rule(
    report_case: ReportCase,
) -> None:
    deal = await report_case.add_deal(users=7, created=kst(2026, 10, 17, 9))
    for hour in (9, 10, 11):
        await report_case.deals.add_action(deal, kst(2026, 10, 20, hour))

    rows = await report_case.rows(
        [
            col("deal.owner", group=True),
            col("deal.users", aggregate="sum"),
            col("deal.status_days", aggregate="avg"),
        ]
    )

    assert rows == [("owner", 7, 10.0)]  # Action 3건이어도 Users 7, 체류 10일(10-17 -> 10-27)


async def test_deal_in_two_groups_counts_once_in_each_group(report_case: ReportCase) -> None:
    deal = await report_case.add_deal(amount=ONE_HUNDRED_MILLION)
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 9), action_type="미팅")
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 10), action_type="미팅")
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 11), action_type="통화")

    result = await report_case.run(
        [
            col("action.type", group=True),
            col("deal.amount", aggregate="sum"),
            col("action.count"),
        ]
    )

    by_type = {row[0]: (row[1], row[2]) for row in result.rows}
    assert by_type == {
        "미팅": (ONE_HUNDRED_MILLION, 2),
        "통화": (ONE_HUNDRED_MILLION, 1),
    }
    assert result.totals is not None
    assert result.totals[1] == ONE_HUNDRED_MILLION  # 합계는 Deal을 전체에서 한 번만 센다


async def test_deal_field_count_counts_each_deal_once_and_action_field_count_counts_actions(
    report_case: ReportCase,
) -> None:
    sap = await report_case.deals.new_vendor("SAP")
    first = await report_case.add_deal(vendor_id=sap.id)
    second = await report_case.add_deal(vendor_id=sap.id)
    for hour in (9, 10, 11):
        await report_case.deals.add_action(first, kst(2026, 10, 5, hour), action=f"x{hour}")
    await report_case.deals.add_action(second, kst(2026, 10, 6), action="y")

    rows = await report_case.rows(
        [
            col("deal.vendor", group=True),
            col("deal.code", aggregate="count"),
            col("deal.code", aggregate="count_distinct"),
            col("action.action", aggregate="count"),
            col("action.count"),
        ]
    )

    assert rows == [("SAP", 2, 2, 4, 4)]  # Deal 필드 건수는 Deal 수, Action 건수는 Action 행 수


async def test_deal_scope_grouping_counts_deals_without_the_once_per_deal_rule(
    report_case: ReportCase,
) -> None:
    sap = await report_case.deals.new_vendor("SAP")
    await report_case.add_deal(vendor_id=sap.id, amount=10)
    await report_case.add_deal(vendor_id=sap.id, amount=30)

    rows = await report_case.rows(
        [
            col("deal.vendor", group=True),
            col("deal.amount", aggregate="sum"),
            col("deal.amount", aggregate="avg"),
            col("deal.code", aggregate="count"),
        ]
    )

    assert rows == [("SAP", 40, 20.0, 2)]


async def test_action_count_leaves_out_deals_without_actions(report_case: ReportCase) -> None:
    with_action = await report_case.add_deal(name="A")
    await report_case.add_deal(name="B")
    await report_case.deals.add_action(with_action, kst(2026, 10, 5))

    rows = await report_case.rows([col("deal.name", group=True), col("action.count")])

    assert rows == [("A", 1)]
