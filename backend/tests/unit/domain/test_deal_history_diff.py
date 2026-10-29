"""Deal History 변경 기록 규칙(R-2, AC-16): 프런트 `diffDeal`(history.test.ts)과 같다.

함께 바뀐 값 표기("계약완료 (Forecast Won과 함께 변경)")는 applyChange와 함께 R3에서 본다.
"""

import dataclasses
from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.deal.values import Poc, PocState, Quote, QuoteSubmitted, RevenueAmount
from tests.factories import later, make_bant, make_deal, make_sync
from tests.support.history_diff import (
    CODE,
    CUSTOMER,
    LABEL_CEO,
    LABEL_FULL_BUDGET,
    OTHER_CUSTOMER,
    PARTNER_1,
    PARTNER_2,
    VENDOR_ORACLE,
    VENDOR_SAP,
    base_deal,
    diff_after,
    edit_of,
    revise_with,
    rows_of,
)
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal


def test_no_change_produces_no_history() -> None:
    assert diff_after(lambda deal: None) == []
    assert diff_after(revise_with) == []


def test_status_change_alone_is_one_status_entry() -> None:
    rows = diff_after(lambda d: revise_with(d, sync=make_sync("introduction", "commit")))

    assert rows == [("status", "Status", "가격협상", "제품소개")]


def test_forecast_change_alone_is_one_forecast_entry() -> None:
    rows = diff_after(lambda d: revise_with(d, sync=make_sync("price_negotiation", "best")))

    assert rows == [("forecast", "Forecast", "Commit", "Best")]


def test_closing_a_deal_records_status_then_forecast_without_a_co_change_note() -> None:
    rows = diff_after(lambda d: revise_with(d, sync=make_sync("contract_completed", "won")))

    assert rows == [
        ("status", "Status", "가격협상", "계약완료"),
        ("forecast", "Forecast", "Commit", "Won"),
    ]


def test_amount_is_written_in_thousand_won_under_unit_target() -> None:
    rows = diff_after(edit_of("revenue_amount", 1_870_000_000))

    assert rows == [("amount", "금액(단위:천원)", "1", "1,870,000")]


def test_amount_change_below_display_unit_records_nothing() -> None:
    rows = diff_after(edit_of("revenue_amount", 1_400))

    assert rows == []


def test_expected_close_is_written_as_an_iso_date() -> None:
    rows = diff_after(edit_of("revenue_date", date(2026, 10, 20)))

    assert rows == [("expectedClose", "Expected Close", "2026-12-01", "2026-10-20")]


def test_owner_uses_the_user_label_of_the_lookup() -> None:
    rows = diff_after(edit_of("owner_user_id", uid("lee")))

    assert rows == [("owner", "Owner", "김영업", "이영업(퇴사)")]


def test_replacing_the_partner_is_one_partner_entry() -> None:
    rows = diff_after(lambda d: d.replace_partner(PARTNER_2, later(5)))  # type: ignore[arg-type]

    assert rows == [("partner", "파트너", "코어테크 민지훈", "에이원시스템 표성호")]


def test_removing_the_partner_is_written_as_none() -> None:
    rows = diff_after(lambda d: d.replace_partner(None, later(5)))

    assert rows == [("partner", "파트너", "코어테크 민지훈", "없음")]


def test_adding_a_first_partner_is_written_from_none() -> None:
    deal = make_deal(code=CODE, customer_id=CUSTOMER)  # type: ignore[arg-type]

    rows = diff_after(lambda d: d.replace_partner(PARTNER_1, later(5)), deal)  # type: ignore[arg-type]

    assert rows == [("partner", "파트너", "없음", "코어테크 민지훈")]


def test_changing_the_customer_contact_is_a_contact_entry() -> None:
    rows = diff_after(lambda d: revise_with(d, customer_id=OTHER_CUSTOMER))

    assert rows == [("contact", "고객 연락처", "한빛은행 정민수", "대한상사 오세훈")]


def test_bant_changes_are_written_per_category_in_category_order() -> None:
    rows = diff_after(
        lambda d: revise_with(d, bant=make_bant(authority=LABEL_CEO, budget=LABEL_FULL_BUDGET))
    )

    assert rows == [
        ("bant", "BANT Label: Budget", "선택 안 함", "풀 예산 확보"),
        ("bant", "BANT Label: Authority", "선택 안 함", "CEO 보고 완료"),
    ]


def test_clearing_a_bant_label_is_written_as_not_selected() -> None:
    deal = base_deal(bant=make_bant(budget=LABEL_FULL_BUDGET))

    rows = diff_after(lambda d: revise_with(d, bant=make_bant()), deal)

    assert rows == [("bant", "BANT Label: Budget", "풀 예산 확보", "선택 안 함")]


@pytest.mark.parametrize(
    ("field", "value", "target", "before", "after"),
    [
        ("name", "B", "Deal Name", "A", "B"),
        ("users", 250, "Users count", "10", "250"),
        ("procurement", "조달청 입찰", "구매절차", "-", "조달청 입찰"),
    ],
)
def test_plain_fields_are_other_entries_named_after_the_field(
    field: str, value: object, target: str, before: str, after: str
) -> None:
    rows = diff_after(edit_of(field, value))

    assert rows == [("other", target, before, after)]


def test_vendor_change_is_recorded_with_names() -> None:
    deal = base_deal(vendor_id=None)

    rows = diff_after(edit_of("vendor_id", VENDOR_SAP), deal)

    assert rows == [("other", "Vendor", "선택 안 함", "SAP")]


def test_solution_change_is_recorded_as_text() -> None:
    deal = base_deal(solution="MFA")

    rows = diff_after(edit_of("solution", "ITDR"), deal)

    assert rows == [("other", "Solution", "MFA", "ITDR")]


def test_legacy_empty_solution_is_shown_as_dash_in_history() -> None:
    """마이그레이션이 채운 ''(레거시 미입력)에서 값으로 바뀔 때만 '-'가 나온다."""
    deal = base_deal()
    object.__setattr__(deal.details, "solution", "")  # 도메인 검증을 거치지 않은 레거시 행
    before = deal.snapshot()
    edit_of("solution", "ITDR")(deal)

    assert rows_of(before, deal.snapshot()) == [("other", "Solution", "-", "ITDR")]


def test_solution_case_only_change_is_recorded() -> None:
    deal = base_deal(solution="itdr")

    rows = diff_after(edit_of("solution", "ITDR"), deal)

    assert rows == [("other", "Solution", "itdr", "ITDR")]


def test_whitespace_only_solution_difference_records_nothing() -> None:
    deal = base_deal(solution="ITDR")

    rows = diff_after(edit_of("solution", "  ITDR  "), deal)

    assert rows == []


def test_unchanged_solution_records_nothing() -> None:
    assert diff_after(edit_of("solution", "S/4HANA")) == []


def test_vendor_change_does_not_record_solution() -> None:
    def change(deal: Deal) -> None:
        revise_with(deal, details=dataclasses.replace(deal.details, vendor_id=VENDOR_ORACLE))

    rows = diff_after(change)

    assert rows == [("other", "Vendor", "SAP", "Oracle")]


def test_clearing_the_vendor_keeps_the_solution_untouched() -> None:
    def clear(deal: Deal) -> None:
        revise_with(deal, details=dataclasses.replace(deal.details, vendor_id=None))

    rows = diff_after(clear)

    assert rows == [("other", "Vendor", "SAP", "선택 안 함")]


def test_unchanged_vendor_records_nothing() -> None:
    assert diff_after(edit_of("vendor_id", VENDOR_SAP)) == []


def test_users_set_to_zero_is_written_as_zero() -> None:
    deal = base_deal(users=5)

    rows = diff_after(edit_of("users", 0), deal)

    assert rows == [("other", "Users count", "5", "0")]


@pytest.mark.parametrize(
    ("quote", "after"),
    [
        (Quote(QuoteSubmitted.YES, date(2026, 10, 1)), "YES (2026-10-01)"),
        (Quote(QuoteSubmitted.NO, None), "NO"),
        (Quote(None, date(2026, 10, 1)), "- (2026-10-01)"),
    ],
)
def test_quote_is_written_as_value_and_optional_date(quote: Quote, after: str) -> None:
    assert diff_after(edit_of("quote", quote)) == [("other", "견적", "-", after)]


@pytest.mark.parametrize(
    ("poc", "after"),
    [
        (Poc(PocState.ING, date(2026, 11, 1)), "ING (2026-11-01)"),
        (Poc(PocState.YES, None), "YES"),
        (Poc(None, date(2026, 11, 1)), "- (2026-11-01)"),
    ],
)
def test_poc_is_written_as_state_and_optional_date(poc: Poc, after: str) -> None:
    assert diff_after(edit_of("poc", poc)) == [("other", "POC", "-", after)]


def _change_everything(deal: Deal) -> None:
    deal.replace_partner(PARTNER_2, later(5))  # type: ignore[arg-type]
    details = dataclasses.replace(
        deal.details,
        name="B",
        vendor_id=VENDOR_ORACLE,
        solution="EBS",
        users=3,
        revenue_amount=RevenueAmount(2_000),
        revenue_date=date(2026, 10, 20),
        owner_user_id=uid("park"),
        quote=Quote(QuoteSubmitted.YES, None),
        poc=Poc(PocState.NO, None),
        procurement="x",
    )
    revise_with(
        deal,
        details=details,
        sync=make_sync("contract_completed", "won"),
        customer_id=OTHER_CUSTOMER,
        bant=make_bant(budget=LABEL_FULL_BUDGET, timeline=LABEL_CEO),
    )


def test_several_changes_are_listed_in_the_fixed_field_order() -> None:
    rows = diff_after(_change_everything)

    assert [(category, target) for category, target, _, _ in rows] == [
        ("status", "Status"),
        ("forecast", "Forecast"),
        ("amount", "금액(단위:천원)"),
        ("expectedClose", "Expected Close"),
        ("owner", "Owner"),
        ("partner", "파트너"),
        ("contact", "고객 연락처"),
        ("bant", "BANT Label: Budget"),
        ("bant", "BANT Label: Timeline"),
        ("other", "Deal Name"),
        ("other", "Vendor"),
        ("other", "Solution"),
        ("other", "Users count"),
        ("other", "견적"),
        ("other", "POC"),
        ("other", "구매절차"),
    ]


def test_every_entry_describes_a_real_change() -> None:
    rows = diff_after(_change_everything)

    assert rows
    assert all(before != after for _, _, before, after in rows)


def test_the_same_snapshot_twice_has_no_difference() -> None:
    deal = base_deal()

    assert rows_of(deal.snapshot(), deal.snapshot()) == []
