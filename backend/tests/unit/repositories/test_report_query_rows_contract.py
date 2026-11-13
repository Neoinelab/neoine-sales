"""ReportQueryRunner(SQL) 계약: 컬럼별 정렬, 행 수, 합계, 표시 이름, 키 기준 고유 건수."""

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest

from app.domain.contact.values import ContactKind
from tests.support.report_defs import col, cond
from tests.support.user_ids import OWNER_ID, uid
from tests.unit.repositories.report_case import kst

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

COUNT = col("deal.code", aggregate="count")


async def _code_names(report_case: ReportCase, kind: str) -> dict[str, str]:
    """코드 key -> 표시 이름 (DB에 시드된 값)."""
    from app.domain.code.values import CodeKind  # noqa: PLC0415

    codes = await report_case.deals.codes.list(CodeKind(kind))
    return {c.key.value: c.name for c in codes}


# ---- 행 수와 total_count ----


async def test_total_count_and_row_limit_for_plain_rows(report_case: ReportCase) -> None:
    """행 수 제한은 돌려주는 행만 자르고 total_count는 제한 전 행 수다.

    테스트 코드: RQ-054
    """
    # given: Deal 105건 (전제: 실제 DB)
    for number in range(105):
        await report_case.add_deal(name=f"d{number:03d}")

    # when: 행 수 100으로 조회한다
    result = await report_case.run([col("deal.name")], row_limit=100)

    # then: 100행을 돌려주고 총 105건이며 정렬 없으면 Deal code 순서다
    assert len(result.rows) == 100
    assert result.total_count == 105
    assert result.rows[0] == ("d000",)  # 정렬이 없으면 Deal code 순서
    assert result.rows[-1] == ("d099",)


async def test_total_count_for_grouped_rows_is_the_group_count(report_case: ReportCase) -> None:
    """그룹핑 조회의 total_count는 그룹 수다.

    테스트 코드: RQ-054
    """
    # given: 이름이 모두 다른 Deal 105건
    for number in range(105):
        await report_case.add_deal(name=f"g{number:03d}")

    # when: 이름 그룹으로 행 수 100 조회한다
    result = await report_case.run([col("deal.name", group=True), COUNT], row_limit=100)

    # then: 100행을 돌려주고 총 105 그룹이다
    assert len(result.rows) == 100
    assert result.total_count == 105


async def test_total_count_counts_groups_not_deals(report_case: ReportCase) -> None:
    """total_count는 Deal 수가 아니라 그룹 수다.

    테스트 코드: RQ-054
    """
    # given: SAP Deal 4건과 IBM Deal 1건
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    for _ in range(4):
        await report_case.add_deal(vendor_id=sap.id)
    await report_case.add_deal(vendor_id=ibm.id)

    # when: Vendor 그룹으로 조회한다
    result = await report_case.run([col("deal.vendor", group=True), COUNT])

    # then: 그룹 2개이고 행도 2개다
    assert result.total_count == 2
    assert len(result.rows) == 2


async def test_zero_rows_give_total_zero(report_case: ReportCase) -> None:
    """결과가 없으면 총 행 수는 0이다.

    테스트 코드: RQ-054
    """
    # when: Deal이 없을 때 조회한다 (전제: 빈 DB)
    result = await report_case.run([col("deal.code")])

    # then: 행이 없고 총 0이다
    assert result.rows == ()
    assert result.total_count == 0


async def test_result_carries_display_sql_and_elapsed_time(report_case: ReportCase) -> None:
    """결과는 입력 값이 보이는 표시 SQL과 소요 시간을 담는다.

    테스트 코드: RQ-059
    """
    # given: Deal 1건
    await report_case.add_deal()

    # when: 검색어 조건으로 조회한다
    result = await report_case.run([col("deal.code")], [cond("deal.name", "contains", "needle")])

    # then: SELECT로 시작하고 검색어가 보이며 소요 시간이 0 이상이다
    assert result.sql.lstrip().upper().startswith("SELECT")
    assert "needle" in result.sql
    assert result.elapsed_ms >= 0


async def test_ungrouped_reports_have_no_totals(report_case: ReportCase) -> None:
    """그룹핑이 없는 조회는 합계 행이 없다.

    테스트 코드: RQ-057
    """
    # given: Deal 1건
    await report_case.add_deal()

    # when: 그룹핑 없이 조회한다
    result = await report_case.run([col("deal.code")])

    # then: 합계 행이 None이다
    assert result.totals is None


# ---- 합계 (totals) ----


async def test_totals_aggregate_number_columns_over_all_matching_rows(
    report_case: ReportCase,
) -> None:
    """합계 행은 조건에 맞는 전체 범위를 그룹 없이 한 번 더 집계한다.

    테스트 코드: RQ-055
    """
    # given: SAP 금액 10·30, IBM 금액 50 Deal
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    await report_case.add_deal(vendor_id=sap.id, amount=10)
    await report_case.add_deal(vendor_id=sap.id, amount=30)
    await report_case.add_deal(vendor_id=ibm.id, amount=50)

    # when: Vendor 그룹과 금액 합계·평균·최소·최대로 조회한다
    result = await report_case.run(
        [
            col("deal.vendor", group=True),
            col("deal.amount", aggregate="sum"),
            col("deal.amount", aggregate="avg"),
            col("deal.amount", aggregate="min"),
            col("deal.amount", aggregate="max"),
        ]
    )

    # then: 합계 행은 그룹 칸 None, 합계 90, 전체 평균 30, 최소 10, 최대 50이다
    assert result.totals == (None, 90, 30.0, 10, 50)  # 평균은 행 평균이 아니라 전체 평균


async def test_totals_are_not_cut_by_the_row_limit(report_case: ReportCase) -> None:
    """합계 행은 행 수 제한에 잘리지 않는다.

    테스트 코드: RQ-055
    """
    # given: 금액 2인 Deal 101건
    for number in range(101):
        await report_case.add_deal(name=f"t{number:03d}", amount=2)

    # when: 이름 그룹으로 행 수 100 조회한다
    result = await report_case.run(
        [col("deal.name", group=True), col("deal.amount", aggregate="sum")], row_limit=100
    )

    # then: 행은 100개이고 합계는 202다
    assert len(result.rows) == 100
    assert result.totals == (None, 202)


async def test_totals_follow_the_same_conditions(report_case: ReportCase) -> None:
    """합계 행은 같은 조건을 따른다.

    테스트 코드: RQ-055
    """
    # given: 조건에 맞는 Deal과 맞지 않는 Deal
    await report_case.add_deal(name="keep", amount=7)
    await report_case.add_deal(name="drop", amount=1000)

    # when: 이름 조건과 그룹핑으로 조회한다
    result = await report_case.run(
        [col("deal.name", group=True), col("deal.amount", aggregate="sum")],
        [cond("deal.name", "equals", "keep")],
    )

    # then: 합계는 맞는 Deal 것만이다
    assert result.totals == (None, 7)


# ---- 정렬 ----


async def test_status_groups_follow_the_code_order_not_the_alphabet(
    report_case: ReportCase,
) -> None:
    """Status 그룹은 이름순이 아니라 코드 순서다.

    테스트 코드: RQ-052
    """
    # given: 서로 다른 Status의 Deal 3건
    await report_case.add_deal(status="poc_completed")
    await report_case.add_deal(status="introduction")
    await report_case.add_deal(status="prospecting")
    columns = [col("deal.status", group=True, sort="asc"), COUNT]
    names = await _code_names(report_case, "status")

    # when: Status 그룹을 오름차순·내림차순·정렬 없이 조회한다
    ascending = await report_case.rows(columns)
    descending = await report_case.rows([col("deal.status", group=True, sort="desc"), COUNT])
    default = await report_case.rows([col("deal.status", group=True), COUNT])

    # then: 오름차순은 코드 순서, 내림차순은 역순, 기본은 오름차순과 같다
    in_order = [names[k] for k in ("prospecting", "introduction", "poc_completed")]
    assert [row[0] for row in ascending] == in_order
    assert [row[0] for row in descending] == in_order[::-1]
    assert default == ascending


async def test_nulls_come_last_in_both_directions(report_case: ReportCase) -> None:
    """NULL 값은 오름차순·내림차순 모두 맨 뒤다.

    테스트 코드: RQ-051
    """
    # given: 파트너사 Acme·Zeta와 파트너 없는 Deal
    acme = await report_case.deals.new_contact(ContactKind.PARTNER, company="Acme")
    zeta = await report_case.deals.new_contact(ContactKind.PARTNER, company="Zeta")
    await report_case.add_deal(partner_id=acme.id)
    await report_case.add_deal(partner_id=zeta.id)
    await report_case.add_deal()

    # when: 파트너사를 오름차순·내림차순으로 조회한다
    ascending = await report_case.rows([col("deal.partner_company", sort="asc")])
    descending = await report_case.rows([col("deal.partner_company", sort="desc")])

    # then: 둘 다 파트너 없음이 마지막이다
    assert [row[0] for row in ascending] == ["Acme", "Zeta", None]
    assert [row[0] for row in descending] == ["Zeta", "Acme", None]


async def test_grouped_rows_can_be_sorted_by_an_aggregate_column(report_case: ReportCase) -> None:
    """그룹핑 조회는 집계 컬럼으로도 정렬한다.

    테스트 코드: RQ-052
    """
    # given: SAP 금액 100, IBM 금액 300 Deal
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    await report_case.add_deal(vendor_id=sap.id, amount=100)
    await report_case.add_deal(vendor_id=ibm.id, amount=300)

    # when: Vendor 그룹과 금액 합계 내림차순으로 조회한다
    rows = await report_case.rows(
        [col("deal.vendor", group=True), col("deal.amount", aggregate="sum", sort="desc")],
    )

    # then: IBM 300, SAP 100 순서다
    assert rows == [("IBM", 300), ("SAP", 100)]


async def test_ties_are_broken_by_deal_code(report_case: ReportCase) -> None:
    """정렬이 같으면 Deal code 순이다.

    테스트 코드: RQ-051
    """
    # given: 이름이 같은 Deal 3건
    for amount in (3, 1, 2):
        await report_case.add_deal(name="Same", amount=amount)

    # when: 이름 내림차순으로 조회한다
    rows = await report_case.rows([col("deal.name", sort="desc"), col("deal.amount")])

    # then: 등록 순서(code 오름차순)로 나온다
    assert rows == [("Same", 3), ("Same", 1), ("Same", 2)]  # 등록 순서 = code 오름차순


async def test_plain_rows_without_sort_are_ordered_by_deal_code(report_case: ReportCase) -> None:
    """정렬이 없으면 Deal code 순이다.

    테스트 코드: RQ-051
    """
    # given: 이름이 b·a·c인 Deal을 이 순서로 등록
    for name in ("b", "a", "c"):
        await report_case.add_deal(name=name)

    # when: 정렬 없이 조회한다
    rows = await report_case.rows([col("deal.name")])

    # then: 등록 순서 그대로다
    assert rows == [("b",), ("a",), ("c",)]


async def test_action_rows_are_ordered_by_acted_on_then_id(report_case: ReportCase) -> None:
    """Action 행의 동률은 수행일, id 순이다(같은 날의 시각은 순서에 쓰이지 않는다).

    테스트 코드: RQ-053
    """
    # given: 늦은 날 Action을 먼저, 이른 날 둘을 나중에(그중 늦은 시각을 먼저) 등록한 Deal
    deal = await report_case.add_deal()
    await report_case.deals.add_action(deal, kst(2026, 10, 6), action="late")
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 15), action="early-first")
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 9), action="early-second")

    # when: Action 컬럼으로 조회한다
    rows = await report_case.rows([col("action.action")])

    # then: 수행일이 이른 것이 먼저고 같은 날은 id(등록) 순이다
    assert rows == [("early-first",), ("early-second",), ("late",)]


async def test_converted_fields_return_dates_not_datetimes(report_case: ReportCase) -> None:
    """최종 업데이트·Status 진입일·수행일·종료일은 시각 없는 date로 조회된다.

    테스트 코드: RQ-113
    """
    # given: 수행하고 종료(수행)한 Next Action이 있는 Deal
    deal = await report_case.add_deal(created=kst(2026, 10, 1, 9))
    action = await report_case.deals.add_action(
        deal, kst(2026, 10, 5, 15), next_action="계획", action="진행"
    )
    await report_case.deals.set_next_action_status(action, "done", kst(2026, 10, 7, 23))

    # when: 네 필드를 조회한다
    (row,) = await report_case.rows(
        [
            col("deal.last_updated_at"),
            col("deal.status_changed_at"),
            col("action.acted_at"),
            col("action.closed_at"),
        ]
    )

    # then: 모두 date이고 datetime이 아니며 값은 업무 날짜다(수행일 10-05, 종료일 10-07)
    assert all(type(value) is date for value in row)
    assert row == (date(2026, 10, 5), date(2026, 10, 1), date(2026, 10, 5), date(2026, 10, 7))


# ---- 표시 이름과 키 기준 ----


async def test_resigned_owner_name_has_the_suffix(report_case: ReportCase) -> None:
    """퇴사한 담당자 이름에는 (퇴사)가 붙는다.

    테스트 코드: RQ-041
    """
    # given: 퇴사한 담당자의 Deal과 재직 담당자의 Deal
    resigned = uid("rep_gone")
    await report_case.add_deal(name="gone", owner=resigned)
    await report_case.add_deal(name="active", owner=OWNER_ID)
    await report_case.deals.resign(resigned, kst(2026, 10, 20))

    # when: Deal 이름과 담당자로 조회한다
    rows = await report_case.rows([col("deal.name"), col("deal.owner")])

    # then: 퇴사자는 이름(퇴사)로 보인다
    assert rows == [("gone", "rep_gone(퇴사)"), ("active", "owner")]


async def test_action_actor_name_is_shown_like_the_owner(report_case: ReportCase) -> None:
    """Action 수행자 이름도 담당자처럼 이름으로 보인다.

    테스트 코드: RQ-041
    """
    # given: 수행자가 있는 Action
    deal = await report_case.add_deal()
    await report_case.deals.add_action(deal, kst(2026, 10, 5), actor_user_id=uid("rep_actor"))

    # when: 수행자 컬럼으로 조회한다
    rows = await report_case.rows([col("action.actor")])

    # then: 수행자 이름이 보인다
    assert rows == [("rep_actor",)]


async def test_customer_columns_show_the_linked_customer(report_case: ReportCase) -> None:
    """고객 컬럼은 연결된 고객 연락처의 회사와 이름을 보인다.

    테스트 코드: RQ-041
    """
    # given: 고객 연락처가 연결된 Deal
    customer = await report_case.deals.new_contact(
        ContactKind.CUSTOMER, company="고객주식회사", name="박고객"
    )
    await report_case.add_deal(customer_id=customer.id)

    # when: 고객사·고객 담당자로 조회한다
    rows = await report_case.rows([col("deal.customer_company"), col("deal.customer_contact")])

    # then: 연결된 연락처의 회사와 이름이다
    assert rows == [("고객주식회사", "박고객")]


async def test_partner_company_uses_only_the_active_link(report_case: ReportCase) -> None:
    """파트너사는 활성 연결의 회사만 보인다.

    테스트 코드: RQ-041
    """
    # given: 파트너를 교체한 Deal, 연결을 해제한 Deal, 연결 없던 Deal
    old = await report_case.deals.new_contact(ContactKind.PARTNER, company="구파트너")
    new = await report_case.deals.new_contact(ContactKind.PARTNER, company="신파트너")
    swapped = await report_case.add_deal(name="swapped", partner_id=old.id)
    unlinked = await report_case.add_deal(name="unlinked", partner_id=old.id)
    await report_case.add_deal(name="never")
    at = kst(2026, 10, 2)
    await report_case.deals.replace_partner(swapped.id, new.id, at)
    await report_case.deals.replace_partner(unlinked.id, None, at + timedelta(minutes=1))

    # when: Deal 이름과 파트너사로 조회한다
    rows = await report_case.rows([col("deal.name"), col("deal.partner_company")])

    # then: 교체한 Deal은 새 파트너, 나머지는 None이다
    assert rows == [("swapped", "신파트너"), ("unlinked", None), ("never", None)]


async def test_count_distinct_uses_keys_not_names(report_case: ReportCase) -> None:
    """고유 건수는 이름이 아니라 key로 센다.

    테스트 코드: RQ-050
    """
    # given: 표시 이름이 같은 담당자 둘의 Deal 3건
    from tests.factories_auth import make_user  # noqa: PLC0415

    first, second = uid("rep_same_a"), uid("rep_same_b")
    for login, user_id in (("rep_same_a", first), ("rep_same_b", second)):
        await report_case.deals.users.add(
            make_user(login, entity_id=user_id, display_name="동명이인")
        )
    await report_case.add_deal(owner=first)
    await report_case.add_deal(owner=second)
    await report_case.add_deal(owner=second)

    # when: 담당자 고유 건수·건수로 조회한다
    rows = await report_case.rows(
        [
            col("deal.status", group=True),
            col("deal.owner", aggregate="count_distinct"),
            col("deal.owner", aggregate="count"),
        ]
    )

    # then: 고유 건수 2, 건수 3이다
    prospecting = (await _code_names(report_case, "status"))["prospecting"]
    assert rows == [(prospecting, 2, 3)]  # 표시 이름이 같아도 id가 다르면 2명


# ---- 값 변환 ----


async def test_result_values_use_plain_python_types(report_case: ReportCase) -> None:
    """결과 값은 정수·소수 둘째 자리·날짜·시각 같은 일반 타입이다.

    테스트 코드: RQ-045
    """
    # given: 금액 10·10·11인 SAP Deal
    from datetime import datetime  # noqa: PLC0415

    sap = await report_case.deals.new_vendor("SAP")
    for amount in (10, 10, 11):
        await report_case.add_deal(vendor_id=sap.id, amount=amount)

    # when: 그룹핑 조회와 단순 조회를 한다
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

    # then: 평균은 소수 둘째 자리(10.33), 타입은 str·int·float·int, 날짜는 date,
    # then: 시각은 오프셋이 있는 datetime, 금액은 int다
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
    """합계 행의 고유 건수는 전체 고유 수이지 그룹 합이 아니다.

    테스트 코드: RQ-056
    """
    # given: 담당자 a가 두 Vendor 그룹에 걸쳐 나오는 Deal 3건
    sap = await report_case.deals.new_vendor("SAP")
    ibm = await report_case.deals.new_vendor("IBM")
    first, second, third = uid("tot_a"), uid("tot_b"), uid("tot_a")
    await report_case.add_deal(vendor_id=sap.id, owner=first)
    await report_case.add_deal(vendor_id=sap.id, owner=second)
    await report_case.add_deal(vendor_id=ibm.id, owner=third)  # 담당자 a가 두 그룹에 나온다

    # when: Vendor 그룹과 담당자 고유 건수·건수로 조회한다
    result = await report_case.run(
        [
            col("deal.vendor", group=True, sort="asc"),
            col("deal.owner", aggregate="count_distinct"),
            col("deal.owner", aggregate="count"),
        ],
    )

    # then: 그룹 행 합은 3이지만 합계 행은 전체 고유 2명, Deal 3건이다
    assert [tuple(r) for r in result.rows] == [("IBM", 1, 1), ("SAP", 2, 2)]  # 그룹 합 = 3
    assert result.totals == (None, 2, 3)  # 전체 고유 담당자 2명, 전체 Deal 3건


async def test_totals_counts_in_action_rows_follow_the_deal_once_and_action_row_rules(
    report_case: ReportCase,
) -> None:
    """Action 행의 합계 행은 Deal당 한 번, Action 필드는 Action 행 수로 센다.

    테스트 코드: RQ-056
    """
    # given: Action 3건이 두 Deal에 걸친 Action 유형별 데이터
    first = await report_case.add_deal(name="A")
    second = await report_case.add_deal(name="B")
    await report_case.deals.add_action(first, kst(2026, 10, 5, 9), action_type="미팅")
    await report_case.deals.add_action(first, kst(2026, 10, 5, 10), action_type="통화")
    await report_case.deals.add_action(second, kst(2026, 10, 6), action_type="미팅")

    # when: Action 유형 그룹과 Deal·Action 건수로 조회한다
    result = await report_case.run(
        [
            col("action.type", group=True),
            col("deal.code", aggregate="count_distinct"),
            col("deal.code", aggregate="count"),
            col("action.action", aggregate="count"),
            col("action.count"),
        ]
    )

    # then: 그룹별 행이 기대대로이고 합계 행은 Deal 2, Action 3이다
    assert [tuple(r) for r in result.rows] == [("미팅", 2, 2, 2, 2), ("통화", 1, 1, 1, 1)]
    # Deal은 두 개뿐(그룹별 고유 건수의 합 3과 다르다), Action 행은 세 개
    assert result.totals == (None, 2, 2, 3, 3)


# ---- 그룹 컬럼만 있는 리포트 ----


@pytest.mark.parametrize("deals", [0, 1, 2, 3])
async def test_group_only_report_has_rows_and_no_totals(
    report_case: ReportCase, deals: int
) -> None:
    """그룹 컬럼뿐인 조회는 행이 있고 합계 행이 없다.

    테스트 코드: RQ-057
    """
    # given: Forecast가 다른 Deal 0~3건 (매개변수)
    for _ in range(deals):
        await report_case.add_deal(forecast="commit")
    if deals:
        await report_case.add_deal(forecast="pipeline")

    # when: Forecast 그룹만으로 조회한다
    result = await report_case.run([col("deal.forecast", group=True)])

    # then: 그룹 행과 총 그룹 수가 기대대로이고 합계 행이 None이다
    names = await _code_names(report_case, "forecast")
    expected = [] if deals == 0 else [(names["pipeline"],), (names["commit"],)]
    assert sorted(tuple(r) for r in result.rows) == sorted(expected)
    assert result.total_count == len(expected)
    assert result.totals is None  # 합계 대상 컬럼이 없다


# ---- 앞 N자는 표시 전용: 그룹핑은 전체 값 ----


async def test_prefix_length_keeps_full_value_grouping(report_case: ReportCase) -> None:
    """앞 N자는 그룹핑에 영향이 없고 전체 값으로 묶는다.

    테스트 코드: RQ-065
    """
    # given: 앞 3자가 같고 전체 이름이 다른 Deal
    await report_case.add_deal(name="ABC-first")
    await report_case.add_deal(name="ABC-second")
    await report_case.add_deal(name="ABC-second")

    # when: 이름 그룹에 앞 N자 3을 주고 조회한다
    rows = await report_case.rows(
        [col("deal.name", group=True, prefix_length=3, sort="asc"), COUNT],
    )

    # then: 전체 이름 기준으로 두 그룹이다
    assert rows == [("ABC-first", 1), ("ABC-second", 2)]


# ---- 컬럼별 정렬: 컬럼 순서가 우선순위 ----


async def _name_partner_deals(report_case: ReportCase) -> None:
    acme = await report_case.deals.new_contact(ContactKind.PARTNER, company="Acme")
    zeta = await report_case.deals.new_contact(ContactKind.PARTNER, company="Zeta")
    await report_case.add_deal(name="a", partner_id=acme.id)
    await report_case.add_deal(name="a", partner_id=zeta.id)
    await report_case.add_deal(name="b", partner_id=acme.id)
    await report_case.add_deal(name="a")


async def test_rows_are_sorted_by_name_then_partner_desc(report_case: ReportCase) -> None:
    """이름 오름차순 뒤 파트너사 내림차순으로 정렬한다.

    테스트 코드: RQ-051
    """
    # given: 이름과 파트너사가 섞인 Deal 4건(a-Acme, a-Zeta, b-Acme, a-파트너 없음)
    await _name_partner_deals(report_case)

    # when: 이름 오름차순·파트너사 내림차순으로 조회한다
    rows = await report_case.rows(
        [col("deal.name", sort="asc"), col("deal.partner_company", sort="desc")]
    )

    # then: 이름 안에서 파트너사가 내림차순이고 NULL이 뒤다
    assert rows == [("a", "Zeta"), ("a", "Acme"), ("a", None), ("b", "Acme")]


async def test_column_order_decides_sort_priority(report_case: ReportCase) -> None:
    """컬럼 순서가 정렬 우선순위를 정한다.

    테스트 코드: RQ-051
    """
    # given: 이름과 파트너사가 섞인 Deal 4건(a-Acme, a-Zeta, b-Acme, a-파트너 없음)
    await _name_partner_deals(report_case)

    # when: 파트너사 내림차순을 먼저, 이름 오름차순을 나중에 조회한다
    rows = await report_case.rows(
        [col("deal.partner_company", sort="desc"), col("deal.name", sort="asc")]
    )

    # then: 파트너사 우선 순서로 나온다
    assert rows == [("Zeta", "a"), ("Acme", "a"), ("Acme", "b"), (None, "a")]


async def test_unsorted_column_does_not_affect_the_order(report_case: ReportCase) -> None:
    """정렬하지 않은 컬럼은 순서에 영향이 없다.

    테스트 코드: RQ-051
    """
    # given: 이름과 파트너사가 섞인 Deal 4건(a-Acme, a-Zeta, b-Acme, a-파트너 없음)
    await _name_partner_deals(report_case)

    # when: 파트너사는 정렬 없이 이름만 내림차순으로 조회한다
    rows = await report_case.rows([col("deal.partner_company"), col("deal.name", sort="desc")])

    # then: 이름 내림차순이다
    assert [row[1] for row in rows] == ["b", "a", "a", "a"]


async def test_ties_after_sort_keys_fall_back_to_deal_code(report_case: ReportCase) -> None:
    """정렬 키가 같으면 Deal code 순으로 돌아간다.

    테스트 코드: RQ-051
    """
    # given: 이름이 같은 Deal 3건
    for amount in (30, 10, 20):
        await report_case.add_deal(name="Same", amount=amount)

    # when: 이름 오름차순으로 조회한다
    rows = await report_case.rows([col("deal.name", sort="asc"), col("deal.amount")])

    # then: 등록 순서다
    assert rows == [("Same", 30), ("Same", 10), ("Same", 20)]  # 등록 순서 = code 오름차순


async def test_row_limit_applies_after_sorting(report_case: ReportCase) -> None:
    """행 수 제한은 정렬 뒤에 적용된다.

    테스트 코드: RQ-054
    """
    # given: Deal 105건
    for number in range(105):
        await report_case.add_deal(name=f"d{number:03d}")

    # when: 이름 내림차순으로 행 수 100 조회한다
    result = await report_case.run([col("deal.name", sort="desc")], row_limit=100)

    # then: 총 105건이고 정렬된 앞 100행이다
    assert result.total_count == 105
    assert result.rows[0] == ("d104",)  # 정렬이 먼저, 제한은 그 뒤
    assert result.rows[-1] == ("d005",)


async def test_grouped_rows_sorted_by_group_then_aggregate(report_case: ReportCase) -> None:
    """그룹 정렬 뒤 같은 그룹 안에서 집계 정렬을 적용한다.

    테스트 코드: RQ-052
    """
    # given: Vendor와 Status가 다른 Deal 4건
    ibm = await report_case.deals.new_vendor("IBM")
    sap = await report_case.deals.new_vendor("SAP")
    await report_case.add_deal(vendor_id=sap.id, status="prospecting", amount=10)
    await report_case.add_deal(vendor_id=sap.id, status="introduction", amount=50)
    await report_case.add_deal(vendor_id=ibm.id, status="prospecting", amount=70)
    await report_case.add_deal(vendor_id=ibm.id, status="introduction", amount=20)
    names = await _code_names(report_case, "status")

    # when: Vendor 오름차순, Status 그룹, 금액 합계 내림차순으로 조회한다
    rows = await report_case.rows(
        [
            col("deal.vendor", group=True, sort="asc"),
            col("deal.status", group=True),
            col("deal.amount", aggregate="sum", sort="desc"),
        ]
    )

    # then: Vendor별로 금액이 큰 Status가 먼저다
    assert rows == [
        ("IBM", names["prospecting"], 70),
        ("IBM", names["introduction"], 20),
        ("SAP", names["introduction"], 50),
        ("SAP", names["prospecting"], 10),
    ]


async def test_grouped_aggregate_sort_before_group_follows_column_order(
    report_case: ReportCase,
) -> None:
    """집계 컬럼이 그룹보다 앞이면 집계 정렬이 먼저다.

    테스트 코드: RQ-052
    """
    # given: 합계가 같은 그룹이 있는 Vendor별 Deal
    ibm = await report_case.deals.new_vendor("IBM")
    sap = await report_case.deals.new_vendor("SAP")
    zed = await report_case.deals.new_vendor("ZED")
    await report_case.add_deal(vendor_id=ibm.id, amount=10)
    await report_case.add_deal(vendor_id=sap.id, amount=4)
    await report_case.add_deal(vendor_id=sap.id, amount=6)
    await report_case.add_deal(vendor_id=zed.id, amount=20)

    # when: 금액 합계 오름차순을 첫 컬럼, Vendor 내림차순을 둘째로 조회한다
    rows = await report_case.rows(
        [
            col("deal.amount", aggregate="sum", sort="asc"),
            col("deal.vendor", group=True, sort="desc"),
        ]
    )

    # then: 합계 순이고 같으면 Vendor 내림차순이다
    assert rows == [(10, "SAP"), (10, "IBM"), (20, "ZED")]
