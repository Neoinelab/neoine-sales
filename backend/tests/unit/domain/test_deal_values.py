"""Deal 값 객체(AC-05): 금액·이름·Vendor 선택·Solution 텍스트·Users count·구매절차·견적·POC·
BANT 선택.

문구는 프런트 목업 `validateDealFields`와 같다. 여기서는 경계값만 본다(순서는 application 테스트).
"""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.errors import InvalidValueError
from app.domain.deal.values import (
    AMOUNT_MAX,
    NAME_MAX,
    PROCUREMENT_MAX,
    USERS_MAX,
    BantSelection,
    Poc,
    PocState,
    Quote,
    QuoteSubmitted,
    RevenueAmount,
    check_users,
)
from app.domain.vendor.values import VendorId
from tests.factories import make_bant, make_deal_details
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.user_ids import OWNER_ID, uid

AMOUNT_MESSAGE = "매출금액은 1원 이상의 정수로 입력하세요."
USERS_MESSAGE = "Users count는 0 이상의 정수로 입력하세요."
USERS_REQUIRED_MESSAGE = "Users count를 입력하세요."
SOLUTION_MAX = 200  # 정본은 app.domain.deal.values.SOLUTION_MAX(아래 테스트가 같은 값인지 확인)


def test_limits_match_the_agreed_values() -> None:
    assert (NAME_MAX, PROCUREMENT_MAX) == (200, 500)
    assert AMOUNT_MAX == 2**53 - 1  # 프런트 Number.isSafeInteger와 같다
    assert USERS_MAX == 2_147_483_647  # PostgreSQL integer 최대


class TestRevenueAmount:
    @pytest.mark.parametrize("value", [1, 1_870_000_000, AMOUNT_MAX])
    def test_accepts_one_up_to_the_largest_safe_integer(self, value: int) -> None:
        assert RevenueAmount(value).value == value

    @pytest.mark.parametrize("value", [0, -1, AMOUNT_MAX + 1, 2**63])
    def test_rejects_zero_negative_and_over_the_safe_maximum(self, value: int) -> None:
        with raises_with(InvalidValueError, AMOUNT_MESSAGE):
            RevenueAmount(value)

    def test_rejects_a_bool_even_though_it_is_an_int(self) -> None:
        with raises_with(InvalidValueError, AMOUNT_MESSAGE):
            RevenueAmount(True)

    @pytest.mark.parametrize("value", [1.5, 100.0, "100", None])
    def test_rejects_a_non_integer_value(self, value: object) -> None:
        with raises_with(InvalidValueError, AMOUNT_MESSAGE):
            RevenueAmount(value)  # type: ignore[arg-type]


class TestDealName:
    def test_is_trimmed(self) -> None:
        assert make_deal_details(name="  ERP 구축  ").name == "ERP 구축"

    @pytest.mark.parametrize("value", ["", "   ", "\t"])
    def test_is_required(self, value: str) -> None:
        with raises_with(InvalidValueError, "Deal Name을 입력하세요."):
            make_deal_details(name=value)

    def test_allows_exactly_the_maximum_length_after_trimming(self) -> None:
        assert make_deal_details(name=f" {'가' * NAME_MAX} ").name == "가" * NAME_MAX

    def test_rejects_one_character_over_the_maximum(self) -> None:
        with raises_with(InvalidValueError, "Deal Name은 200자 이내로 입력하세요."):
            make_deal_details(name="가" * (NAME_MAX + 1))

    def test_rejects_a_nul_character(self) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_details(name="a\x00b")


class TestVendorChoice:
    """Deal은 등록된 Vendor의 id만 갖는다. Vendor 이름 규칙은 vendor 도메인이다."""

    def test_vendor_is_kept(self) -> None:
        vendor_id = VendorId(new_id())

        assert make_deal_details(vendor_id=vendor_id).vendor_id == vendor_id

    def test_no_vendor_is_allowed(self) -> None:
        assert make_deal_details().vendor_id is None

    def test_the_old_text_vendor_field_is_gone(self) -> None:
        with pytest.raises(TypeError):
            make_deal_details(vendor="SAP")

    def test_the_old_solution_id_field_is_gone(self) -> None:
        with pytest.raises(TypeError):
            make_deal_details(solution_id=1)


class TestSolutionText:
    """Solution은 Vendor와 무관한 필수 자유 텍스트다(AC-6~8, Q1 변경)."""

    def test_solution_is_trimmed(self) -> None:
        assert make_deal_details(solution="  ITDR  ").solution == "ITDR"

    def test_constructor_allows_the_legacy_empty_solution(self) -> None:
        # 리뷰 후속 결정: 빈 값 거절은 입력 검증(check_solution)이 맡고, 값 객체는 NUL·길이만 본다.
        assert make_deal_details(solution="").solution == ""

    def test_replace_on_a_legacy_empty_solution_details_succeeds(self) -> None:
        legacy = make_deal_details(solution="")

        changed = replace(
            legacy, revenue_amount=RevenueAmount(2_000), revenue_date=date(2027, 1, 5)
        )

        assert (changed.revenue_amount.value, changed.revenue_date) == (2_000, date(2027, 1, 5))
        assert changed.solution == ""

    def test_replace_keeps_checking_the_solution_length(self) -> None:
        with raises_with(InvalidValueError, "Solution은 200자 이내로 입력하세요."):
            replace(make_deal_details(solution="ITDR"), solution="a" * (SOLUTION_MAX + 1))

    def test_solution_keeps_letter_case(self) -> None:
        assert make_deal_details(solution="itDR").solution == "itDR"

    def test_solution_allows_200_and_rejects_201(self) -> None:
        assert make_deal_details(solution="a" * SOLUTION_MAX).solution == "a" * SOLUTION_MAX
        with raises_with(InvalidValueError, "Solution은 200자 이내로 입력하세요."):
            make_deal_details(solution="a" * (SOLUTION_MAX + 1))

    def test_length_is_counted_after_trimming(self) -> None:
        details = make_deal_details(solution=f" {'a' * SOLUTION_MAX} ")

        assert details.solution == "a" * SOLUTION_MAX

    def test_solution_limit_constant_is_200(self) -> None:
        from app.domain.deal import values  # noqa: PLC0415 - 구현 전에도 다른 테스트가 수집되게

        assert values.SOLUTION_MAX == SOLUTION_MAX

    def test_check_solution_rejects_blank_and_returns_the_trimmed_text(self) -> None:
        from app.domain.deal.values import check_solution  # noqa: PLC0415

        assert check_solution("  ITDR ") == "ITDR"
        with raises_with(InvalidValueError, "Solution을 입력하세요."):
            check_solution("   ")

    def test_solution_with_nul_is_rejected(self) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_details(solution="a\x00b")

    def test_solution_without_vendor_is_allowed(self) -> None:
        details = make_deal_details(vendor_id=None, solution="ITDR")

        assert (details.vendor_id, details.solution) == (None, "ITDR")

    def test_solution_with_vendor_is_kept(self) -> None:
        vendor_id = VendorId(new_id())

        details = make_deal_details(vendor_id=vendor_id, solution="ITDR")

        assert (details.vendor_id, details.solution) == (vendor_id, "ITDR")


class TestUsers:
    @pytest.mark.parametrize("value", [0, 1, 250, USERS_MAX])
    def test_accepts_zero_up_to_the_int_maximum(self, value: int) -> None:
        assert make_deal_details(users=value).users == value

    @pytest.mark.parametrize("value", [-1, USERS_MAX + 1, 1.5, True])
    def test_rejects_negative_over_the_int_maximum_a_fraction_and_a_bool(
        self, value: object
    ) -> None:
        with raises_with(InvalidValueError, USERS_MESSAGE):
            make_deal_details(users=value)

    def test_missing_users_is_rejected_with_the_required_message(self) -> None:
        with raises_with(InvalidValueError, USERS_REQUIRED_MESSAGE):
            make_deal_details(users=None)

    @pytest.mark.parametrize("value", [0, 1, USERS_MAX])
    def test_check_users_accepts_zero_up_to_the_maximum(self, value: int) -> None:
        assert check_users(value) == value

    def test_check_users_none_is_required(self) -> None:
        with raises_with(InvalidValueError, USERS_REQUIRED_MESSAGE):
            check_users(None)

    @pytest.mark.parametrize("value", [-1, USERS_MAX + 1, 1.5, True])
    def test_check_users_rejects_out_of_range_values(self, value: object) -> None:
        with raises_with(InvalidValueError, USERS_MESSAGE):
            check_users(value)


class TestProcurement:
    def test_defaults_to_an_empty_text_and_is_trimmed(self) -> None:
        assert make_deal_details().procurement == ""
        assert make_deal_details(procurement="  조달청 입찰  ").procurement == "조달청 입찰"

    def test_a_blank_text_is_stored_as_empty(self) -> None:
        assert make_deal_details(procurement="   ").procurement == ""

    def test_allows_the_limit_and_rejects_one_over(self) -> None:
        make_deal_details(procurement="가" * PROCUREMENT_MAX)
        with raises_with(InvalidValueError, "구매절차는 500자 이내로 입력하세요."):
            make_deal_details(procurement="가" * (PROCUREMENT_MAX + 1))


class TestDealDetails:
    def test_keeps_the_owner_as_a_user_id_and_the_amount_as_a_value_object(self) -> None:
        details = make_deal_details()

        assert details.owner_user_id == OWNER_ID
        assert details.revenue_amount == RevenueAmount(150_000_000)
        assert details.revenue_date == date(2026, 6, 30)
        assert not hasattr(details, "revenue")  # Money(통화) 모델은 없다
        assert not hasattr(details, "code")  # code는 Deal의 식별자다

    def test_owner_user_id_is_kept_as_given(self) -> None:
        assert make_deal_details(owner_user_id=uid("someone")).owner_user_id == uid("someone")

    def test_is_comparable_by_value(self) -> None:
        assert make_deal_details() == make_deal_details()
        assert make_deal_details(name="다른 딜") != make_deal_details()


class TestQuoteAndPoc:
    def test_enum_values_are_the_wire_values(self) -> None:
        assert {m.value for m in QuoteSubmitted} == {"YES", "NO"}
        assert {m.value for m in PocState} == {"YES", "ING", "NO"}

    @pytest.mark.parametrize(
        ("submitted", "submitted_date"),
        [
            (None, None),
            (QuoteSubmitted.YES, date(2026, 10, 1)),
            (QuoteSubmitted.YES, None),
            (QuoteSubmitted.NO, date(2026, 10, 1)),  # 교차 검증 없음(Q7)
            (None, date(2026, 10, 1)),
        ],
    )
    def test_quote_accepts_any_combination_of_value_and_date(
        self, submitted: QuoteSubmitted | None, submitted_date: date | None
    ) -> None:
        quote = Quote(submitted=submitted, submitted_date=submitted_date)

        assert (quote.submitted, quote.submitted_date) == (submitted, submitted_date)

    @pytest.mark.parametrize(
        ("state", "completed_date"),
        [
            (None, None),
            (PocState.YES, date(2026, 11, 1)),
            (PocState.ING, date(2026, 11, 1)),  # 교차 검증 없음(Q7)
            (PocState.NO, None),
            (None, date(2026, 11, 1)),
        ],
    )
    def test_poc_accepts_any_combination_of_state_and_date(
        self, state: PocState | None, completed_date: date | None
    ) -> None:
        poc = Poc(state=state, completed_date=completed_date)

        assert (poc.state, poc.completed_date) == (state, completed_date)

    def test_details_keep_the_quote_and_poc(self) -> None:
        quote = Quote(submitted=QuoteSubmitted.YES, submitted_date=date(2026, 10, 1))
        poc = Poc(state=PocState.ING, completed_date=None)

        details = make_deal_details(quote=quote, poc=poc)

        assert (details.quote, details.poc) == (quote, poc)


class TestBantSelection:
    def test_has_one_label_or_none_per_category(self) -> None:
        label = BantLabelId(new_id())

        selection = make_bant(budget=label)

        assert selection.get(BantCategory.BUDGET) == label
        others = [selection.get(c) for c in BantCategory if c is not BantCategory.BUDGET]
        assert others == [None, None, None]

    def test_with_replaces_one_category_and_keeps_the_original(self) -> None:
        first, second = BantLabelId(new_id()), BantLabelId(new_id())
        original = make_bant(budget=first, need=second)

        changed = original.with_(BantCategory.NEED, None)

        assert changed.get(BantCategory.NEED) is None
        assert changed.get(BantCategory.BUDGET) == first
        assert original.get(BantCategory.NEED) == second  # 원본은 그대로

    def test_equal_selections_compare_equal(self) -> None:
        label = BantLabelId(new_id())

        assert make_bant(timeline=label) == BantSelection(
            budget=None, authority=None, need=None, timeline=label
        )
