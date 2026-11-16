"""Deal History 변경 기록 규칙(R-2): 프런트 `diffDeal`(history.test.ts)과 같다.

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
    """바뀐 것이 없으면 이력이 0건이다.

    테스트 코드: DD-042
    """
    # when: 변경 없이 비교한다
    assert diff_after(lambda deal: None) == []
    # then: 빈 목록이다
    assert diff_after(revise_with) == []


def test_status_change_alone_is_one_status_entry() -> None:
    """Status만 바뀌면 status 이력 한 건이다.

    테스트 코드: DD-042
    """
    # when: Status만 바꿔 비교한다
    rows = diff_after(lambda d: revise_with(d, sync=make_sync("introduction", "commit")))

    # then: 구분 status, 대상 Status, 코드 이름 전후 한 건이다
    assert rows == [("status", "Status", "가격협상", "제품소개")]


def test_forecast_change_alone_is_one_forecast_entry() -> None:
    """Forecast만 바뀌면 forecast 이력 한 건이다.

    테스트 코드: DD-042
    """
    # when: Forecast만 바꿔 비교한다
    rows = diff_after(lambda d: revise_with(d, sync=make_sync("price_negotiation", "best")))

    # then: 구분 forecast, 대상 Forecast 한 건이다
    assert rows == [("forecast", "Forecast", "Commit", "Best")]


def test_closing_a_deal_records_status_then_forecast_without_a_co_change_note() -> None:
    """폼으로 두 값을 함께 바꾸면 Status, Forecast 순서로 남고 함께 변경 표기가 없다.

    테스트 코드: DD-010, DD-042
    """
    # when: 계약완료·Won으로 바꿔 비교한다
    rows = diff_after(lambda d: revise_with(d, sync=make_sync("contract_completed", "won")))

    # then: Status, Forecast 두 건이고 괄호 표기가 없다
    assert rows == [
        ("status", "Status", "가격협상", "계약완료"),
        ("forecast", "Forecast", "Commit", "Won"),
    ]


def test_amount_is_written_in_won_under_unit_target() -> None:
    """금액 이력은 대상 '금액(단위:원)'에 원 콤마 숫자로 남는다.

    테스트 코드: DD-027
    """
    # when: 금액을 바꿔 비교한다
    rows = diff_after(edit_of("revenue_amount", 1_870_000_000))

    # then: 구분 amount, 1,000에서 1,870,000,000이다
    assert rows == [("amount", "금액(단위:원)", "1,000", "1,870,000,000")]


def test_small_amount_change_is_recorded_without_rounding() -> None:
    """작은 금액 차이도 반올림 없이 기록한다.

    테스트 코드: DD-027
    """
    # when: 금액을 1,400으로 바꿔 비교한다
    rows = diff_after(edit_of("revenue_amount", 1_400))

    # then: 1,000에서 1,400 그대로다
    assert rows == [("amount", "금액(단위:원)", "1,000", "1,400")]


def test_expected_close_is_written_as_an_iso_date() -> None:
    """Expected Close 이력은 YYYY-MM-DD로 남는다.

    테스트 코드: DD-029
    """
    # when: Expected Close를 바꿔 비교한다
    rows = diff_after(edit_of("revenue_date", date(2026, 10, 20)))

    # then: 구분 expectedClose, ISO 날짜 전후다
    assert rows == [("expectedClose", "Expected Close", "2026-12-01", "2026-10-20")]


def test_owner_uses_the_user_label_of_the_lookup() -> None:
    """Owner 이력은 사용자 표기(퇴사자는 '(퇴사)')로 남는다.

    테스트 코드: DD-043
    """
    # when: Owner를 바꿔 비교한다
    rows = diff_after(edit_of("owner_user_id", uid("lee")))

    # then: 구분 owner, 김영업에서 이영업(퇴사)다
    assert rows == [("owner", "Owner", "김영업", "이영업(퇴사)")]


def test_replacing_the_partner_is_one_partner_entry() -> None:
    """파트너 교체는 '회사 담당자' 표기의 partner 이력 한 건이다.

    테스트 코드: DD-043
    """
    # when: 파트너를 교체해 비교한다
    rows = diff_after(lambda d: d.replace_partner(PARTNER_2, later(5)))  # type: ignore[arg-type]

    # then: 구분 partner, 대상 파트너, 이전·새 파트너 표기 한 건이다
    assert rows == [("partner", "파트너", "코어테크 민지훈", "에이원시스템 표성호")]


def test_removing_the_partner_is_written_as_none() -> None:
    """파트너 제거는 변경 후가 '없음'이다.

    테스트 코드: DD-043
    """
    # when: 파트너를 제거해 비교한다
    rows = diff_after(lambda d: d.replace_partner(None, later(5)))

    # then: 변경 후가 '없음'이다
    assert rows == [("partner", "파트너", "코어테크 민지훈", "없음")]


def test_adding_a_first_partner_is_written_from_none() -> None:
    """첫 파트너 추가는 변경 전이 '없음'이다.

    테스트 코드: DD-043
    """
    # given: 파트너가 없는 Deal
    deal = make_deal(code=CODE, customer_id=CUSTOMER, vendor_id=VENDOR_SAP)  # type: ignore[arg-type]

    # when: 파트너를 추가해 비교한다
    rows = diff_after(lambda d: d.replace_partner(PARTNER_1, later(5)), deal)  # type: ignore[arg-type]

    # then: 변경 전이 '없음'이다
    assert rows == [("partner", "파트너", "없음", "코어테크 민지훈")]


def test_changing_the_customer_contact_is_a_contact_entry() -> None:
    """고객 연락처 변경은 '회사 담당자' 표기의 contact 이력이다.

    테스트 코드: DD-043
    """
    # when: 고객 연락처를 바꿔 비교한다
    rows = diff_after(lambda d: revise_with(d, customer_id=OTHER_CUSTOMER))

    # then: 구분 contact, 대상 고객 연락처, 전후 표기다
    assert rows == [("contact", "고객 연락처", "한빛은행 정민수", "대한상사 오세훈")]


def test_bant_changes_are_written_per_category_in_category_order() -> None:
    """BANT 이력은 구분마다 한 건씩 Budget, Authority 순서로 남는다.

    테스트 코드: DD-044
    """
    # when: Authority와 Budget Label을 선택해 비교한다
    rows = diff_after(
        lambda d: revise_with(d, bant=make_bant(authority=LABEL_CEO, budget=LABEL_FULL_BUDGET))
    )

    # then: Budget, Authority 순서 두 건이고 변경 전은 '선택 안 함'이다
    assert rows == [
        ("bant", "BANT Label: Budget", "선택 안 함", "풀 예산 확보"),
        ("bant", "BANT Label: Authority", "선택 안 함", "CEO 보고 완료"),
    ]


def test_clearing_a_bant_label_is_written_as_not_selected() -> None:
    """BANT Label을 비우면 변경 후가 '선택 안 함'이다.

    테스트 코드: DD-044
    """
    # given: Budget Label이 선택된 Deal
    deal = base_deal(bant=make_bant(budget=LABEL_FULL_BUDGET))

    # when: Label을 비워 비교한다
    rows = diff_after(lambda d: revise_with(d, bant=make_bant()), deal)

    # then: 변경 후가 '선택 안 함'이다
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
    """이름·Users count·구매절차는 필드 이름이 대상인 other 이력으로 남는다.

    테스트 코드: DD-045
    """
    # when: 해당 필드를 바꿔 비교한다
    rows = diff_after(edit_of(field, value))

    # then: 구분 other, 대상은 필드 이름, 전후는 정해진 표기다
    assert rows == [("other", target, before, after)]


def test_vendor_change_is_recorded_with_names() -> None:
    """Vendor 변경은 이전·이후 Vendor 이름으로 남는다.

    테스트 코드: DD-045
    """
    # given: Vendor가 Oracle인 Deal
    deal = base_deal(vendor_id=VENDOR_ORACLE)

    # when: Vendor를 SAP로 바꿔 비교한다
    rows = diff_after(edit_of("vendor_id", VENDOR_SAP), deal)

    # then: 대상 Vendor, Oracle에서 SAP다
    assert rows == [("other", "Vendor", "Oracle", "SAP")]


def test_product_change_is_recorded_as_text() -> None:
    """Product 변경은 텍스트 그대로 남는다.

    테스트 코드: DD-045
    """
    # given: Product가 MFA인 Deal
    deal = base_deal(product="MFA")

    # when: ITDR로 바꿔 비교한다
    rows = diff_after(edit_of("product", "ITDR"), deal)

    # then: 대상 Product, MFA에서 ITDR다
    assert rows == [("other", "Product", "MFA", "ITDR")]


def test_empty_product_is_shown_as_dash_in_history() -> None:
    """빈 Product는 이력에 '-'로 나온다(값 → 빈 값, 빈 값 → 값 모두).

    테스트 코드: DD-045
    """
    # given: Product가 ITDR인 Deal과 빈 Deal
    filled = base_deal(product="ITDR")
    empty = base_deal(product="")

    # when: ITDR를 비우는 변경과 빈 값에 ITDR를 넣는 변경을 비교한다
    cleared = diff_after(edit_of("product", ""), filled)
    entered = diff_after(edit_of("product", "ITDR"), empty)

    # then: 빈 쪽이 '-'다
    assert cleared == [("other", "Product", "ITDR", "-")]
    assert entered == [("other", "Product", "-", "ITDR")]


def test_product_case_only_change_is_recorded() -> None:
    """대소문자만 바뀐 Product도 바뀐 것으로 기록한다.

    테스트 코드: DD-045
    """
    # given: Product가 itdr인 Deal
    deal = base_deal(product="itdr")

    # when: ITDR로 바꿔 비교한다
    rows = diff_after(edit_of("product", "ITDR"), deal)

    # then: itdr에서 ITDR 한 건이다
    assert rows == [("other", "Product", "itdr", "ITDR")]


def test_whitespace_only_product_difference_records_nothing() -> None:
    """앞뒤 공백만 다른 Product는 바뀐 것이 아니다.

    테스트 코드: DD-042
    """
    # given: Product가 ITDR인 Deal
    deal = base_deal(product="ITDR")

    # when: 앞뒤 공백을 붙여 같은 값으로 바꿔 비교한다
    rows = diff_after(edit_of("product", "  ITDR  "), deal)

    # then: 이력이 없다
    assert rows == []


def test_unchanged_product_records_nothing() -> None:
    """같은 Product면 이력이 없다.

    테스트 코드: DD-042
    """
    # when: 같은 Product로 비교한다
    actual = diff_after(edit_of("product", "S/4HANA"))
    # then: 빈 목록이다
    assert actual == []


def test_vendor_change_does_not_record_product() -> None:
    """Vendor만 바뀌면 Product 이력은 남지 않는다.

    테스트 코드: DD-045
    """

    def change(deal: Deal) -> None:
        revise_with(deal, details=dataclasses.replace(deal.details, vendor_id=VENDOR_ORACLE))

    # when: Vendor만 SAP에서 Oracle로 바꿔 비교한다
    rows = diff_after(change)

    # then: Vendor 이력 한 건뿐이다
    assert rows == [("other", "Vendor", "SAP", "Oracle")]


def test_unchanged_vendor_records_nothing() -> None:
    """같은 Vendor면 이력이 없다.

    테스트 코드: DD-042
    """
    # when: 같은 Vendor로 비교한다
    actual = diff_after(edit_of("vendor_id", VENDOR_SAP))
    # then: 빈 목록이다
    assert actual == []


def test_users_set_to_zero_is_written_as_zero() -> None:
    """Users count를 0으로 바꾸면 0으로 남는다.

    테스트 코드: DD-045
    """
    # given: Users count가 5인 Deal
    deal = base_deal(users=5)

    # when: 0으로 바꿔 비교한다
    rows = diff_after(edit_of("users", 0), deal)

    # then: 5에서 0이다
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
    """견적 이력은 'YES|NO|-'와 있으면 제출일로 남는다.

    테스트 코드: DD-045
    """
    # when: 견적을 바꿔 비교한다
    actual = diff_after(edit_of("quote", quote))
    # then: 대상 견적, 변경 후가 값[ (날짜)] 표기다
    assert actual == [("other", "견적", "-", after)]


@pytest.mark.parametrize(
    ("poc", "after"),
    [
        (Poc(PocState.ING, date(2026, 11, 1)), "ING (2026-11-01)"),
        (Poc(PocState.YES, None), "YES"),
        (Poc(None, date(2026, 11, 1)), "- (2026-11-01)"),
    ],
)
def test_poc_is_written_as_state_and_optional_date(poc: Poc, after: str) -> None:
    """POC 이력은 'YES|ING|NO|-'와 있으면 완료일로 남는다.

    테스트 코드: DD-045
    """
    # when: POC를 바꿔 비교한다
    actual = diff_after(edit_of("poc", poc))
    # then: 대상 POC, 변경 후가 상태[ (날짜)] 표기다
    assert actual == [("other", "POC", "-", after)]


def _change_everything(deal: Deal) -> None:
    deal.replace_partner(PARTNER_2, later(5))  # type: ignore[arg-type]
    details = dataclasses.replace(
        deal.details,
        name="B",
        vendor_id=VENDOR_ORACLE,
        product="EBS",
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
    """여러 필드가 바뀌면 고정 순서로 한 건씩 나열한다.

    테스트 코드: DD-042
    """
    # when: 비교한다
    rows = diff_after(_change_everything)

    # then: Status부터 구매절차까지 고정 순서의 16건이다
    assert [(category, target) for category, target, _, _ in rows] == [
        ("status", "Status"),
        ("forecast", "Forecast"),
        ("amount", "금액(단위:원)"),
        ("expectedClose", "Expected Close"),
        ("owner", "Owner"),
        ("partner", "파트너"),
        ("contact", "고객 연락처"),
        ("bant", "BANT Label: Budget"),
        ("bant", "BANT Label: Timeline"),
        ("other", "Deal Name"),
        ("other", "Vendor"),
        ("other", "Product"),
        ("other", "Users count"),
        ("other", "견적"),
        ("other", "POC"),
        ("other", "구매절차"),
    ]


def test_every_entry_describes_a_real_change() -> None:
    """모든 이력 항목은 전후가 다른 실제 변경이다.

    테스트 코드: DD-042
    """
    # when: 비교한다
    rows = diff_after(_change_everything)

    # then: 항목마다 변경 전과 변경 후가 다르다
    assert rows
    assert all(before != after for _, _, before, after in rows)


def test_the_same_snapshot_twice_has_no_difference() -> None:
    """같은 스냅숏끼리는 차이가 없다.

    테스트 코드: DD-042
    """
    # given: Deal 하나
    deal = base_deal()

    # when: 같은 스냅숏 둘을 비교한다
    actual = rows_of(deal.snapshot(), deal.snapshot())
    # then: 이력이 없다
    assert actual == []
