"""ReportQueryRunner(SQL) 계약: 정렬, 행 수, 합계, 표시 이름, 키 기준 고유 건수 (AC1, AC7, AC13)."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from app.domain.contact.values import ContactKind
from tests.support.report_defs import col, cond
from tests.support.user_ids import OWNER_ID, uid
from tests.unit.repositories.report_case import kst

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

COUNT = col("deal.code", aggregate="count")


# ---- 행 수와 total_count ----


async def test_total_count_and_row_limit_for_plain_rows(report_case: ReportCase) -> None:
    for number in range(105):
        await report_case.add_deal(name=f"d{number:03d}")

    result = await report_case.run([col("deal.name")], row_limit=100)

    assert len(result.rows) == 100
    assert result.total_count == 105
    assert result.rows[0] == ("d000",)  # 정렬이 없으면 Deal code 순서
    assert result.rows[-1] == ("d099",)


async def test_total_count_for_grouped_rows_is_the_group_count(report_case: ReportCase) -> None:
    for number in range(105):
        await report_case.add_deal(name=f"g{number:03d}")

    result = await report_case.run([col("deal.name", group=True), COUNT], row_limit=100)

    assert len(result.rows) == 100
    assert result.total_count == 105


async def test_total_count_counts_groups_not_deals(report_case: ReportCase) -> None:
    sap = await report_case.deals.new_vendor("SAP")
    for _ in range(4):
        await report_case.add_deal(vendor_id=sap.id)
    await report_case.add_deal()

    result = await report_case.run([col("deal.vendor", group=True), COUNT])

    assert result.total_count == 2
    assert len(result.rows) == 2


async def test_zero_rows_give_total_zero(report_case: ReportCase) -> None:
    result = await report_case.run([col("deal.code")])

    assert result.rows == ()
    assert result.total_count == 0


async def test_result_carries_display_sql_and_elapsed_time(report_case: ReportCase) -> None:
    await report_case.add_deal()

    result = await report_case.run([col("deal.code")], [cond("deal.name", "contains", "needle")])

    assert result.sql.lstrip().upper().startswith("SELECT")
    assert "needle" in result.sql
    assert result.elapsed_ms >= 0


async def test_ungrouped_reports_have_no_totals(report_case: ReportCase) -> None:
    await report_case.add_deal()

    result = await report_case.run([col("deal.code")])

    assert result.totals is None


# ---- 합계 (totals) ----


async def test_totals_aggregate_number_columns_over_all_matching_rows(
    report_case: ReportCase,
) -> None:
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    await report_case.add_deal(vendor_id=sap.id, amount=10)
    await report_case.add_deal(vendor_id=sap.id, amount=30)
    await report_case.add_deal(vendor_id=ibm.id, amount=50)

    result = await report_case.run(
        [
            col("deal.vendor", group=True),
            col("deal.amount", aggregate="sum"),
            col("deal.amount", aggregate="avg"),
            col("deal.amount", aggregate="min"),
            col("deal.amount", aggregate="max"),
        ]
    )

    assert result.totals == (None, 90, 30.0, 10, 50)  # 평균은 행 평균이 아니라 전체 평균


async def test_totals_are_not_cut_by_the_row_limit(report_case: ReportCase) -> None:
    for number in range(101):
        await report_case.add_deal(name=f"t{number:03d}", amount=2)

    result = await report_case.run(
        [col("deal.name", group=True), col("deal.amount", aggregate="sum")], row_limit=100
    )

    assert len(result.rows) == 100
    assert result.totals == (None, 202)


async def test_totals_follow_the_same_conditions(report_case: ReportCase) -> None:
    await report_case.add_deal(name="keep", amount=7)
    await report_case.add_deal(name="drop", amount=1000)

    result = await report_case.run(
        [col("deal.name", group=True), col("deal.amount", aggregate="sum")],
        [cond("deal.name", "equals", "keep")],
    )

    assert result.totals == (None, 7)


# ---- 정렬 ----


async def test_status_groups_follow_the_code_order_not_the_alphabet(
    report_case: ReportCase,
) -> None:
    await report_case.add_deal(status="poc_completed")
    await report_case.add_deal(status="introduction")
    await report_case.add_deal(status="prospecting")
    columns = [col("deal.status", group=True, format="key"), COUNT]

    ascending = await report_case.rows(columns, sort={"column": 0, "direction": "asc"})
    descending = await report_case.rows(columns, sort={"column": 0, "direction": "desc"})
    default = await report_case.rows(columns)

    assert [row[0] for row in ascending] == ["prospecting", "introduction", "poc_completed"]
    assert [row[0] for row in descending] == ["poc_completed", "introduction", "prospecting"]
    assert default == ascending


async def test_nulls_come_last_in_both_directions(report_case: ReportCase) -> None:
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    await report_case.add_deal(vendor_id=sap.id)
    await report_case.add_deal(vendor_id=ibm.id)
    await report_case.add_deal()
    columns = [col("deal.vendor", group=True), COUNT]

    ascending = await report_case.rows(columns, sort={"column": 0, "direction": "asc"})
    descending = await report_case.rows(columns, sort={"column": 0, "direction": "desc"})

    assert [row[0] for row in ascending] == ["IBM", "SAP", None]
    assert [row[0] for row in descending] == ["SAP", "IBM", None]


async def test_grouped_rows_can_be_sorted_by_an_aggregate_column(report_case: ReportCase) -> None:
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    await report_case.add_deal(vendor_id=sap.id, amount=100)
    await report_case.add_deal(vendor_id=ibm.id, amount=300)

    rows = await report_case.rows(
        [col("deal.vendor", group=True), col("deal.amount", aggregate="sum")],
        sort={"column": 1, "direction": "desc"},
    )

    assert rows == [("IBM", 300), ("SAP", 100)]


async def test_ties_are_broken_by_deal_code(report_case: ReportCase) -> None:
    for amount in (3, 1, 2):
        await report_case.add_deal(name="Same", amount=amount)

    rows = await report_case.rows(
        [col("deal.name"), col("deal.amount")], sort={"column": 0, "direction": "desc"}
    )

    assert rows == [("Same", 3), ("Same", 1), ("Same", 2)]  # 등록 순서 = code 오름차순


async def test_plain_rows_without_sort_are_ordered_by_deal_code(report_case: ReportCase) -> None:
    for name in ("b", "a", "c"):
        await report_case.add_deal(name=name)

    rows = await report_case.rows([col("deal.name")])

    assert rows == [("b",), ("a",), ("c",)]


async def test_action_rows_are_ordered_by_acted_at_then_id(report_case: ReportCase) -> None:
    deal = await report_case.add_deal()
    await report_case.deals.add_action(deal, kst(2026, 10, 6), action="late")
    await report_case.deals.add_action(deal, kst(2026, 10, 5), action="early")

    rows = await report_case.rows([col("action.action")])

    assert rows == [("early",), ("late",)]


# ---- 표시 이름과 키 기준 ----


async def test_resigned_owner_name_has_the_suffix(report_case: ReportCase) -> None:
    resigned = uid("rep_gone")
    await report_case.add_deal(name="gone", owner=resigned)
    await report_case.add_deal(name="active", owner=OWNER_ID)
    await report_case.deals.resign(resigned, kst(2026, 10, 20))

    rows = await report_case.rows([col("deal.name"), col("deal.owner")])

    assert rows == [("gone", "rep_gone(퇴사)"), ("active", "owner")]


async def test_action_actor_name_is_shown_like_the_owner(report_case: ReportCase) -> None:
    deal = await report_case.add_deal()
    await report_case.deals.add_action(deal, kst(2026, 10, 5), actor_user_id=uid("rep_actor"))

    rows = await report_case.rows([col("action.actor")])

    assert rows == [("rep_actor",)]


async def test_customer_columns_show_the_linked_customer(report_case: ReportCase) -> None:
    customer = await report_case.deals.new_contact(
        ContactKind.CUSTOMER, company="고객주식회사", name="박고객"
    )
    await report_case.add_deal(customer_id=customer.id)

    rows = await report_case.rows([col("deal.customer_company"), col("deal.customer_contact")])

    assert rows == [("고객주식회사", "박고객")]


async def test_partner_company_uses_only_the_active_link(report_case: ReportCase) -> None:
    old = await report_case.deals.new_contact(ContactKind.PARTNER, company="구파트너")
    new = await report_case.deals.new_contact(ContactKind.PARTNER, company="신파트너")
    swapped = await report_case.add_deal(name="swapped", partner_id=old.id)
    unlinked = await report_case.add_deal(name="unlinked", partner_id=old.id)
    await report_case.add_deal(name="never")
    at = kst(2026, 10, 2)
    await report_case.deals.replace_partner(swapped.id, new.id, at)
    await report_case.deals.replace_partner(unlinked.id, None, at + timedelta(minutes=1))

    rows = await report_case.rows([col("deal.name"), col("deal.partner_company")])

    assert rows == [("swapped", "신파트너"), ("unlinked", None), ("never", None)]


async def test_count_distinct_uses_keys_not_names(report_case: ReportCase) -> None:
    from tests.factories_auth import make_user  # noqa: PLC0415

    first, second = uid("rep_same_a"), uid("rep_same_b")
    for login, user_id in (("rep_same_a", first), ("rep_same_b", second)):
        await report_case.deals.users.add(
            make_user(login, entity_id=user_id, display_name="동명이인")
        )
    await report_case.add_deal(owner=first)
    await report_case.add_deal(owner=second)
    await report_case.add_deal(owner=second)

    rows = await report_case.rows(
        [
            col("deal.status", group=True, format="key"),
            col("deal.owner", aggregate="count_distinct"),
            col("deal.owner", aggregate="count"),
        ]
    )

    assert rows == [("prospecting", 2, 3)]  # 표시 이름이 같아도 id가 다르면 2명


# ---- 값 변환 ----


async def test_result_values_use_plain_python_types(report_case: ReportCase) -> None:
    from datetime import date, datetime  # noqa: PLC0415

    sap = await report_case.deals.new_vendor("SAP")
    for amount in (10, 10, 11):
        await report_case.add_deal(vendor_id=sap.id, amount=amount)

    grouped = await report_case.rows(
        [
            col("deal.vendor", group=True),
            col("deal.amount", aggregate="sum"),
            col("deal.amount", aggregate="avg"),
            COUNT,
        ]
    )
    plain = await report_case.rows(
        [col("deal.expected_close"), col("deal.created_at"), col("deal.amount")]
    )

    assert grouped == [("SAP", 31, 10.33, 3)]  # avg는 소수 둘째 자리 반올림
    assert [type(v) for v in grouped[0]] == [str, int, float, int]
    assert type(plain[0][0]) is date
    assert isinstance(plain[0][1], datetime)
    assert plain[0][1].tzinfo is not None
    assert type(plain[0][2]) is int


# ---- 합계(totals)의 count·count_distinct ----


async def test_totals_count_distinct_is_the_overall_distinct_count_not_the_sum_of_groups(
    report_case: ReportCase,
) -> None:
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    first, second, third = uid("tot_a"), uid("tot_b"), uid("tot_a")
    await report_case.add_deal(vendor_id=sap.id, owner=first)
    await report_case.add_deal(vendor_id=sap.id, owner=second)
    await report_case.add_deal(vendor_id=ibm.id, owner=third)  # 담당자 a가 두 그룹에 나온다

    result = await report_case.run(
        [
            col("deal.vendor", group=True),
            col("deal.owner", aggregate="count_distinct"),
            col("deal.owner", aggregate="count"),
        ],
        sort={"column": 0, "direction": "asc"},
    )

    assert [tuple(r) for r in result.rows] == [("IBM", 1, 1), ("SAP", 2, 2)]  # 그룹 합 = 3
    assert result.totals == (None, 2, 3)  # 전체 고유 담당자 2명, 전체 Deal 3건


async def test_totals_counts_in_action_rows_follow_the_deal_once_and_action_row_rules(
    report_case: ReportCase,
) -> None:
    first = await report_case.add_deal(name="A")
    second = await report_case.add_deal(name="B")
    await report_case.deals.add_action(first, kst(2026, 10, 5, 9), action_type="미팅")
    await report_case.deals.add_action(first, kst(2026, 10, 5, 10), action_type="통화")
    await report_case.deals.add_action(second, kst(2026, 10, 6), action_type="미팅")

    result = await report_case.run(
        [
            col("action.type", group=True),
            col("deal.code", aggregate="count_distinct"),
            col("deal.code", aggregate="count"),
            col("action.action", aggregate="count"),
            col("action.count"),
        ]
    )

    assert [tuple(r) for r in result.rows] == [("미팅", 2, 2, 2, 2), ("통화", 1, 1, 1, 1)]
    # Deal은 두 개뿐(그룹별 고유 건수의 합 3과 다르다), Action 행은 세 개
    assert result.totals == (None, 2, 2, 3, 3)


# ---- 그룹 컬럼만 있는 리포트 ----


@pytest.mark.parametrize("deals", [0, 1, 2, 3])
async def test_group_only_report_has_rows_and_no_totals(
    report_case: ReportCase, deals: int
) -> None:
    for _ in range(deals):
        await report_case.add_deal(forecast="commit")
    if deals:
        await report_case.add_deal(forecast="pipeline")

    result = await report_case.run([col("deal.forecast", group=True, format="key")])

    expected = [] if deals == 0 else [("pipeline",), ("commit",)]
    assert sorted(tuple(r) for r in result.rows) == sorted(expected)
    assert result.total_count == len(expected)
    assert result.totals is None  # 합계 대상 컬럼이 없다
