"""ReportQueryRunner(SQL) 계약: 행 범위(Action 행/Deal 행)와 Deal당 한 번 규칙."""

from typing import TYPE_CHECKING

from tests.support.report_defs import col, cond
from tests.unit.repositories.report_case import kst

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

ONE_HUNDRED_MILLION = 100_000_000


async def test_action_column_gives_one_row_per_action_and_drops_deals_without_actions(
    report_case: ReportCase,
) -> None:
    """Action 컬럼이 있으면 Action 1건이 한 행이고 Action 없는 Deal은 빠진다.

    테스트 코드: RQ-028
    """
    # given: Action 3건인 Deal A와 Action 없는 Deal B
    with_actions = await report_case.add_deal(name="A")
    await report_case.add_deal(name="B")
    for hour, text in ((9, "a1"), (10, "a2"), (11, "a3")):
        await report_case.deals.add_action(with_actions, kst(2026, 10, 5, hour), action=text)

    # when: Deal 이름과 Action 진행사항으로 조회한다
    rows = await report_case.rows([col("deal.name"), col("action.action")])

    # then: A의 Action 3행뿐이다
    assert rows == [("A", "a1"), ("A", "a2"), ("A", "a3")]


async def test_action_condition_only_keeps_one_row_per_matching_deal(
    report_case: ReportCase,
) -> None:
    """Action 필드가 조건에만 있으면 맞는 Action이 있는 Deal만 한 번씩 나온다.

    테스트 코드: RQ-029
    """
    # given: 미팅 Action이 2건인 A, 통화 Action인 B, Action 없는 C
    meeting = await report_case.type_id("미팅")
    first = await report_case.add_deal(name="A")
    second = await report_case.add_deal(name="B")
    await report_case.add_deal(name="C")
    await report_case.deals.add_action(first, kst(2026, 10, 5), action_type="미팅")
    await report_case.deals.add_action(first, kst(2026, 10, 6), action_type="미팅")
    await report_case.deals.add_action(second, kst(2026, 10, 7), action_type="통화")

    # when: Deal 이름 컬럼과 Action 유형 미팅 조건으로 조회한다
    result = await report_case.run([col("deal.name")], [cond("action.type", "in", [meeting])])

    # then: A 한 행이고 총 1건이다
    assert [tuple(r) for r in result.rows] == [("A",)]
    assert result.total_count == 1


async def test_and_requires_one_action_to_meet_all_action_conditions(
    report_case: ReportCase,
) -> None:
    """AND면 한 Action이 모든 Action 조건을 만족해야 하고 OR이면 하나면 된다.

    테스트 코드: RQ-030
    """
    # given: 9월 미팅 Action과 이번 달 통화 Action을 가진 Deal
    meeting = await report_case.type_id("미팅")
    deal = await report_case.add_deal(name="A")
    await report_case.deals.add_action(deal, kst(2026, 9, 10), action_type="미팅")
    await report_case.deals.add_action(deal, kst(2026, 10, 15), action_type="통화")
    conditions = [
        cond("action.type", "in", [meeting]),
        cond("action.acted_at", "relative", {"period": "this_month"}),
    ]

    # when: 미팅 조건과 이번 달 조건을 AND와 OR로 각각 조회한다
    anded = await report_case.rows([col("deal.name")], conditions, combine="and")
    ored = await report_case.rows([col("deal.name")], conditions, combine="or")

    # then: AND는 없고 OR은 그 Deal이다
    assert anded == []  # 미팅은 9월, 이번 달 Action은 통화라서 한 Action이 둘 다 맞지 않는다
    assert ored == [("A",)]


async def test_or_mixes_deal_conditions_with_the_exists_of_action_conditions(
    report_case: ReportCase,
) -> None:
    """OR는 Deal 조건과 Action 조건 중 하나만 맞아도 고른다.

    테스트 코드: RQ-030
    """
    # given: Deal 조건에 맞는 Deal, Action 조건에 맞는 Deal, 둘 다 아닌 Deal
    meeting = await report_case.type_id("미팅")
    await report_case.add_deal(name="Match")
    by_action = await report_case.add_deal(name="Other")
    await report_case.add_deal(name="Neither")
    await report_case.deals.add_action(by_action, kst(2026, 10, 5), action_type="미팅")

    # when: 이름 조건과 Action 유형 조건을 OR로 조회한다
    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.name", "equals", "match"), cond("action.type", "in", [meeting])],
        combine="or",
    )

    # then: 앞의 둘이다
    assert rows == [("Match",), ("Other",)]


async def test_and_combines_a_deal_condition_with_the_action_exists(
    report_case: ReportCase,
) -> None:
    """AND는 Deal 조건과 Action 조건을 모두 만족하는 Deal만 고른다.

    테스트 코드: RQ-030
    """
    # given: 둘 다 미팅 Action이 있는 Deal Keep과 Drop
    meeting = await report_case.type_id("미팅")
    keep = await report_case.add_deal(name="Keep")
    drop = await report_case.add_deal(name="Drop")
    await report_case.deals.add_action(keep, kst(2026, 10, 5), action_type="미팅")
    await report_case.deals.add_action(drop, kst(2026, 10, 5), action_type="미팅")

    # when: 이름 keep 조건과 Action 유형 조건을 AND로 조회한다
    rows = await report_case.rows(
        [col("deal.name")],
        [cond("deal.name", "equals", "keep"), cond("action.type", "in", [meeting])],
    )

    # then: Keep 하나다
    assert rows == [("Keep",)]


async def test_no_conditions_returns_every_deal(report_case: ReportCase) -> None:
    """조건이 없으면 모든 Deal이 나온다.

    테스트 코드: RQ-031
    """
    # given: Deal 둘
    await report_case.add_deal(name="A")
    await report_case.add_deal(name="B")

    # when: 조건 없이 조회한다
    rows = await report_case.rows([col("deal.name")])

    # then: 두 Deal 모두 나온다
    assert rows == [("A",), ("B",)]


async def test_deal_amount_is_summed_once_per_deal_in_action_rows(
    report_case: ReportCase,
) -> None:
    """Action 행 그룹핑에서 Deal 금액 집계는 Deal당 한 번이고 Action 건수는 Action 수다.

    테스트 코드: RQ-047
    """
    # given: Action 3건인 Deal(1억)과 Action 2건인 Deal(3억)
    first = await report_case.add_deal(amount=ONE_HUNDRED_MILLION)
    second = await report_case.add_deal(amount=3 * ONE_HUNDRED_MILLION)
    for hour in (9, 10, 11):
        await report_case.deals.add_action(first, kst(2026, 10, 5, hour))
    for hour in (9, 10):
        await report_case.deals.add_action(second, kst(2026, 10, 6, hour))

    # when: 담당자 그룹과 금액 합계·평균·최소·최대·Action 건수로 조회한다
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

    # then: 합계 4억, 평균 2억, 최소 1억, 최대 3억이고 Action 건수는 5다
    assert rows == [
        ("owner", 4 * ONE_HUNDRED_MILLION, 2 * ONE_HUNDRED_MILLION, 100_000_000, 300_000_000, 5)
    ]


async def test_deal_users_and_status_days_follow_the_once_per_deal_rule(
    report_case: ReportCase,
) -> None:
    """Users count와 체류 일수도 Deal당 한 번이다.

    테스트 코드: RQ-048
    """
    # given: Users 7, 10일 전 등록, Action 3건인 Deal
    deal = await report_case.add_deal(users=7, created=kst(2026, 10, 17, 9))
    for hour in (9, 10, 11):
        await report_case.deals.add_action(deal, kst(2026, 10, 20, hour))

    # when: 담당자 그룹과 Users 합계·체류 일수 평균으로 조회한다
    rows = await report_case.rows(
        [
            col("deal.owner", group=True),
            col("deal.users", aggregate="sum"),
            col("deal.status_days", aggregate="avg"),
        ]
    )

    # then: Users 7, 체류 10일이다
    assert rows == [("owner", 7, 10.0)]  # Action 3건이어도 Users count 7, 체류 10일(10-17 -> 10-27)


async def test_deal_in_two_groups_counts_once_in_each_group(report_case: ReportCase) -> None:
    """한 Deal이 두 그룹에 있으면 그룹마다 한 번씩 센다.

    테스트 코드: RQ-049
    """
    # given: 미팅 Action 2건과 통화 Action 1건을 가진 Deal
    deal = await report_case.add_deal(amount=ONE_HUNDRED_MILLION)
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 9), action_type="미팅")
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 10), action_type="미팅")
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 11), action_type="통화")

    # when: Action 유형 그룹과 금액 합계·Action 건수로 조회한다
    result = await report_case.run(
        [
            col("action.type", group=True),
            col("deal.amount", aggregate="sum"),
            col("action.count"),
        ]
    )

    # then: 두 그룹 모두 금액은 1억이고 Action 건수는 2와 1이며 합계 행은 1억이다
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
    """Deal 필드 건수는 Deal당 한 번이고 Action 필드 건수는 Action마다다.

    테스트 코드: RQ-048
    """
    # given: Action 3건과 1건을 가진 SAP Deal 둘
    sap = await report_case.deals.new_vendor("SAP")
    first = await report_case.add_deal(vendor_id=sap.id)
    second = await report_case.add_deal(vendor_id=sap.id)
    for hour in (9, 10, 11):
        await report_case.deals.add_action(first, kst(2026, 10, 5, hour), action=f"x{hour}")
    await report_case.deals.add_action(second, kst(2026, 10, 6), action="y")

    # when: Vendor 그룹과 Deal code 건수·고유 건수, 진행사항 건수, Action 건수로 조회한다
    rows = await report_case.rows(
        [
            col("deal.vendor", group=True),
            col("deal.code", aggregate="count"),
            col("deal.code", aggregate="count_distinct"),
            col("action.action", aggregate="count"),
            col("action.count"),
        ]
    )

    # then: Deal 필드 건수는 2·2, Action 필드 건수는 4·4다
    assert rows == [("SAP", 2, 2, 4, 4)]  # Deal 필드 건수는 Deal 수, Action 건수는 Action 행 수


async def test_deal_scope_grouping_counts_deals_without_the_once_per_deal_rule(
    report_case: ReportCase,
) -> None:
    """Deal 행 범위 그룹핑은 Deal 행 그대로 집계한다.

    테스트 코드: RQ-047
    """
    # given: 금액 10과 30인 SAP Deal 둘
    sap = await report_case.deals.new_vendor("SAP")
    await report_case.add_deal(vendor_id=sap.id, amount=10)
    await report_case.add_deal(vendor_id=sap.id, amount=30)

    # when: Vendor 그룹과 금액 합계·평균, Deal code 건수로 조회한다
    rows = await report_case.rows(
        [
            col("deal.vendor", group=True),
            col("deal.amount", aggregate="sum"),
            col("deal.amount", aggregate="avg"),
            col("deal.code", aggregate="count"),
        ]
    )

    # then: 합계 40, 평균 20, 건수 2다
    assert rows == [("SAP", 40, 20.0, 2)]


async def test_action_count_leaves_out_deals_without_actions(report_case: ReportCase) -> None:
    """Action 건수는 Action 없는 Deal을 결과에서 뺀다.

    테스트 코드: RQ-028
    """
    # given: Action 1건인 Deal A와 Action 없는 Deal B
    with_action = await report_case.add_deal(name="A")
    await report_case.add_deal(name="B")
    await report_case.deals.add_action(with_action, kst(2026, 10, 5))

    # when: Deal 이름 그룹과 Action 건수로 조회한다
    rows = await report_case.rows([col("deal.name", group=True), col("action.count")])

    # then: A의 1건뿐이다
    assert rows == [("A", 1)]
