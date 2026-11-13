"""Deal 값 객체: 금액·이름·Vendor 선택·Solution 텍스트·Users count·구매절차·견적·POC·
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
    """길이·금액·Users 한도가 합의한 값과 같다."""
    # when·then: 이름 200, 구매절차 500, 금액 2^53-1, Users 정수 최대다
    assert (NAME_MAX, PROCUREMENT_MAX) == (200, 500)
    assert AMOUNT_MAX == 2**53 - 1  # 프런트 Number.isSafeInteger와 같다
    assert USERS_MAX == 2_147_483_647  # PostgreSQL integer 최대


class TestRevenueAmount:
    @pytest.mark.parametrize("value", [1, 1_870_000_000, AMOUNT_MAX])
    def test_accepts_one_up_to_the_largest_safe_integer(self, value: int) -> None:
        """매출금액은 1부터 안전한 최대 정수까지 허용된다."""
        # when: 경계 값으로 만든다
        result = RevenueAmount(value).value
        # then: 그대로 보관한다
        assert result == value

    @pytest.mark.parametrize("value", [0, -1, AMOUNT_MAX + 1, 2**63])
    def test_rejects_zero_negative_and_over_the_safe_maximum(self, value: int) -> None:
        """0, 음수, 안전한 최대 정수 초과 금액은 거절된다."""
        # when·then: 범위 밖 금액이면 금액 안내 InvalidValueError다
        with raises_with(InvalidValueError, AMOUNT_MESSAGE):
            RevenueAmount(value)

    def test_rejects_a_bool_even_though_it_is_an_int(self) -> None:
        """bool은 int의 하위형이어도 금액으로 거절된다."""
        # when·then: True로 만들면 금액 안내 InvalidValueError다
        with raises_with(InvalidValueError, AMOUNT_MESSAGE):
            RevenueAmount(True)

    @pytest.mark.parametrize("value", [1.5, 100.0, "100", None])
    def test_rejects_a_non_integer_value(self, value: object) -> None:
        """실수·문자열·None은 금액으로 거절된다."""
        # when·then: 정수가 아닌 값이면 금액 안내 InvalidValueError다
        with raises_with(InvalidValueError, AMOUNT_MESSAGE):
            RevenueAmount(value)  # type: ignore[arg-type]


class TestDealName:
    def test_is_trimmed(self) -> None:
        """Deal 이름은 앞뒤 공백을 자른다."""
        # when: 공백 낀 이름으로 만든다
        result = make_deal_details(name="  ERP 구축  ").name
        # then: 잘린 이름이다
        assert result == "ERP 구축"

    @pytest.mark.parametrize("value", ["", "   ", "\t"])
    def test_is_required(self, value: str) -> None:
        """Deal 이름은 필수다."""
        # when·then: 빈 값·공백 이름이면 필수 안내 InvalidValueError다
        with raises_with(InvalidValueError, "Deal Name을 입력하세요."):
            make_deal_details(name=value)

    def test_allows_exactly_the_maximum_length_after_trimming(self) -> None:
        """Deal 이름은 공백을 자른 뒤 200자까지 허용된다."""
        # when: 공백 포함 200자 이름으로 만든다
        result = make_deal_details(name=f" {'가' * NAME_MAX} ").name
        # then: 잘라서 200자이므로 허용된다
        assert result == "가" * NAME_MAX

    def test_rejects_one_character_over_the_maximum(self) -> None:
        """Deal 이름이 200자를 1자 넘으면 거절된다."""
        # when·then: 201자 이름이면 길이 안내 InvalidValueError다
        with raises_with(InvalidValueError, "Deal Name은 200자 이내로 입력하세요."):
            make_deal_details(name="가" * (NAME_MAX + 1))

    def test_rejects_a_nul_character(self) -> None:
        """Deal 이름에 NUL 문자가 있으면 거절된다."""
        # when·then: NUL이 든 이름이면 InvalidValueError다
        with pytest.raises(InvalidValueError):
            make_deal_details(name="a\x00b")


def _vendor_required_message() -> str:
    import importlib  # noqa: PLC0415

    return str(importlib.import_module("app.domain.deal.errors").VENDOR_REQUIRED_MESSAGE)


class TestVendorChoice:
    """Deal은 등록된 Vendor의 id만 갖는다. Vendor 이름 규칙은 vendor 도메인이다."""

    def test_vendor_is_kept(self) -> None:
        """Deal은 선택한 Vendor id를 보관한다."""
        # given: Vendor id
        vendor_id = VendorId(new_id())

        # when: 그 Vendor로 만든다
        result = make_deal_details(vendor_id=vendor_id).vendor_id
        # then: vendor_id가 그대로다
        assert result == vendor_id

    def test_vendor_id_is_a_required_non_null_field(self) -> None:
        """Deal 상세의 vendor_id는 null을 허용하지 않는 필수 필드다.

        테스트 코드: DE-116
        """
        import typing  # noqa: PLC0415

        from app.domain.deal.values import DealDetails  # noqa: PLC0415

        # when: DealDetails의 vendor_id 타입 힌트를 읽는다
        hint = typing.get_type_hints(DealDetails)["vendor_id"]

        # then: VendorId 그대로이고(None 불허) 안내 문구 상수가 정해져 있다
        assert hint is VendorId
        assert _vendor_required_message() == "Vendor를 선택하세요."

    def test_the_old_text_vendor_field_is_gone(self) -> None:
        """예전 텍스트 vendor 필드는 더 이상 받지 않는다."""
        # when·then: vendor 인자를 주면 TypeError다
        with pytest.raises(TypeError):
            make_deal_details(vendor="SAP")

    def test_the_old_solution_id_field_is_gone(self) -> None:
        """예전 solution_id 필드는 더 이상 받지 않는다."""
        # when·then: solution_id 인자를 주면 TypeError다
        with pytest.raises(TypeError):
            make_deal_details(solution_id=1)


class TestSolutionText:
    """Solution은 Vendor와 무관한 선택 자유 텍스트다(2026-11-13 변경, 빈 값 '')."""

    def test_solution_is_trimmed(self) -> None:
        """Solution은 앞뒤 공백을 자른다."""
        # when: 공백 낀 Solution으로 만든다
        result = make_deal_details(solution="  ITDR  ").solution
        # then: 잘린 값이다
        assert result == "ITDR"

    def test_constructor_allows_the_empty_solution(self) -> None:
        """값 객체 생성자는 빈 Solution을 허용한다."""
        # Solution은 선택이라 빈 값 ''이 정상 값이다. 값 객체는 NUL·길이만 본다.
        # when: 빈 Solution으로 만든다
        result = make_deal_details(solution="").solution
        # then: 빈 문자열로 보관된다
        assert result == ""

    def test_replace_on_an_empty_solution_details_succeeds(self) -> None:
        """빈 Solution인 상세도 다른 필드를 replace할 수 있다."""
        # given: 빈 Solution의 상세
        legacy = make_deal_details(solution="")

        # when: 금액·매출일을 replace로 바꾼다
        changed = replace(
            legacy, revenue_amount=RevenueAmount(2_000), revenue_date=date(2027, 1, 5)
        )

        # then: 바뀐 값이 반영되고 Solution은 빈 값 그대로다
        assert (changed.revenue_amount.value, changed.revenue_date) == (2_000, date(2027, 1, 5))
        assert changed.solution == ""

    def test_replace_keeps_checking_the_solution_length(self) -> None:
        """replace로 Solution을 바꿀 때도 길이 제한을 검사한다."""
        # when·then: 201자 Solution으로 replace하면 길이 안내 InvalidValueError다
        with raises_with(InvalidValueError, "Solution은 200자 이내로 입력하세요."):
            replace(make_deal_details(solution="ITDR"), solution="a" * (SOLUTION_MAX + 1))

    def test_solution_keeps_letter_case(self) -> None:
        """Solution은 대소문자를 그대로 보관한다."""
        # when: 대소문자 섞인 Solution으로 만든다
        result = make_deal_details(solution="itDR").solution
        # then: 그대로다
        assert result == "itDR"

    def test_solution_allows_200_and_rejects_201(self) -> None:
        """Solution은 200자까지 허용하고 201자는 거절한다."""
        # when: 200자 Solution으로 만든다
        result = make_deal_details(solution="a" * SOLUTION_MAX).solution
        # then: 그대로 보관한다
        assert result == "a" * SOLUTION_MAX
        # when·then: 201자 Solution이면 길이 안내 InvalidValueError다
        with raises_with(InvalidValueError, "Solution은 200자 이내로 입력하세요."):
            make_deal_details(solution="a" * (SOLUTION_MAX + 1))

    def test_length_is_counted_after_trimming(self) -> None:
        """Solution 길이는 앞뒤 공백을 자른 뒤 센다."""
        # when: 공백 포함 202자(자르면 200자) Solution으로 만든다
        details = make_deal_details(solution=f" {'a' * SOLUTION_MAX} ")

        # then: 200자로 보관된다
        assert details.solution == "a" * SOLUTION_MAX

    def test_solution_limit_constant_is_200(self) -> None:
        """Solution 길이 상수의 정본 값이 200이다."""
        from app.domain.deal import values  # noqa: PLC0415 - 구현 전에도 다른 테스트가 수집되게

        # when·then: 도메인 SOLUTION_MAX가 200이다
        assert values.SOLUTION_MAX == SOLUTION_MAX

    def test_check_solution_returns_the_trimmed_text_and_empty_for_blank(self) -> None:
        """check_solution은 잘린 텍스트를 돌려주고 빈 값·공백뿐이면 오류 없이 빈 문자열을 돌려준다.

        테스트 코드: DE-115
        """
        from app.domain.deal.values import check_solution  # noqa: PLC0415

        # when: 앞뒤 공백 낀 값, 빈 값, 공백만, 탭을 검사한다
        trimmed = check_solution("  ITDR ")
        blanks = [check_solution(raw) for raw in ("", "   ", "\t")]

        # then: 잘린 텍스트와 빈 문자열이다(입력 안내 오류 없음)
        assert trimmed == "ITDR"
        assert blanks == ["", "", ""]

    def test_check_solution_still_rejects_201_characters(self) -> None:
        """check_solution은 200자 초과를 여전히 거절한다.

        테스트 코드: DE-017
        """
        from app.domain.deal.values import check_solution  # noqa: PLC0415

        # when·then: 201자 Solution이면 길이 안내 InvalidValueError다
        with raises_with(InvalidValueError, "Solution은 200자 이내로 입력하세요."):
            check_solution("a" * (SOLUTION_MAX + 1))

    def test_solution_with_nul_is_rejected(self) -> None:
        """Solution에 NUL 문자가 있으면 거절된다."""
        # when·then: NUL이 든 Solution이면 InvalidValueError다
        with pytest.raises(InvalidValueError):
            make_deal_details(solution="a\x00b")

    def test_empty_solution_with_a_vendor_is_kept(self) -> None:
        """Vendor만 있고 Solution이 빈 값인 상세를 만들 수 있다."""
        # given: Vendor id
        vendor_id = VendorId(new_id())

        # when: Solution 없이 Vendor만 넣어 만든다
        details = make_deal_details(vendor_id=vendor_id, solution="")

        # then: Vendor는 보관되고 Solution은 ''다
        assert (details.vendor_id, details.solution) == (vendor_id, "")

    def test_solution_with_vendor_is_kept(self) -> None:
        """Vendor와 Solution을 함께 주면 둘 다 보관한다."""
        # given: Vendor id
        vendor_id = VendorId(new_id())

        # when: Vendor와 Solution을 함께 넣어 만든다
        details = make_deal_details(vendor_id=vendor_id, solution="ITDR")

        # then: 둘 다 그대로 보관된다
        assert (details.vendor_id, details.solution) == (vendor_id, "ITDR")


class TestUsers:
    @pytest.mark.parametrize("value", [0, 1, 250, USERS_MAX])
    def test_accepts_zero_up_to_the_int_maximum(self, value: int) -> None:
        """Users count는 0부터 정수 최대값까지 허용된다."""
        # when: 경계 값으로 만든다
        result = make_deal_details(users=value).users
        # then: 그대로 보관한다
        assert result == value

    @pytest.mark.parametrize("value", [-1, USERS_MAX + 1, 1.5, True])
    def test_rejects_negative_over_the_int_maximum_a_fraction_and_a_bool(
        self, value: object
    ) -> None:
        """음수, 정수 최대 초과, 실수, bool은 Users count로 거절된다."""
        # when·then: 범위 밖 값이면 Users 안내 InvalidValueError다
        with raises_with(InvalidValueError, USERS_MESSAGE):
            make_deal_details(users=value)

    def test_missing_users_is_rejected_with_the_required_message(self) -> None:
        """Users count가 없으면 필수 안내로 거절된다."""
        # when·then: None이면 필수 안내 InvalidValueError다
        with raises_with(InvalidValueError, USERS_REQUIRED_MESSAGE):
            make_deal_details(users=None)

    @pytest.mark.parametrize("value", [0, 1, USERS_MAX])
    def test_check_users_accepts_zero_up_to_the_maximum(self, value: int) -> None:
        """check_users는 0부터 최대값까지 그 값을 돌려준다."""
        # when: 경계 값을 검사한다
        result = check_users(value)
        # then: 같은 값이 돌아온다
        assert result == value

    def test_check_users_none_is_required(self) -> None:
        """check_users는 None을 필수 안내로 거절한다."""
        # when·then: None을 검사하면 필수 안내 InvalidValueError다
        with raises_with(InvalidValueError, USERS_REQUIRED_MESSAGE):
            check_users(None)

    @pytest.mark.parametrize("value", [-1, USERS_MAX + 1, 1.5, True])
    def test_check_users_rejects_out_of_range_values(self, value: object) -> None:
        """check_users는 범위 밖 값을 거절한다."""
        # when·then: 범위 밖 값을 검사하면 Users 안내 InvalidValueError다
        with raises_with(InvalidValueError, USERS_MESSAGE):
            check_users(value)


class TestProcurement:
    def test_defaults_to_an_empty_text_and_is_trimmed(self) -> None:
        """구매절차는 기본이 빈 문자열이고 앞뒤 공백을 자른다."""
        # when: 기본값과 공백 낀 값으로 각각 만든다
        result_1 = make_deal_details().procurement
        result_2 = make_deal_details(procurement="  조달청 입찰  ").procurement
        # then: 기본값은 빈 문자열이고 공백 낀 값은 잘린다
        assert result_1 == ""
        assert result_2 == "조달청 입찰"

    def test_a_blank_text_is_stored_as_empty(self) -> None:
        """공백만인 구매절차는 빈 문자열로 저장된다."""
        # when: 공백만 넣는다
        result = make_deal_details(procurement="   ").procurement
        # then: 빈 문자열이다
        assert result == ""

    def test_allows_the_limit_and_rejects_one_over(self) -> None:
        """구매절차는 500자까지 허용하고 501자는 거절한다."""
        # when·then: 500자는 허용된다
        make_deal_details(procurement="가" * PROCUREMENT_MAX)
        # when·then: 501자면 길이 안내 InvalidValueError다
        with raises_with(InvalidValueError, "구매절차는 500자 이내로 입력하세요."):
            make_deal_details(procurement="가" * (PROCUREMENT_MAX + 1))


class TestDealDetails:
    def test_keeps_the_owner_as_a_user_id_and_the_amount_as_a_value_object(self) -> None:
        """Deal 상세는 담당자를 사용자 id로, 금액을 값 객체로 보관한다."""
        # when: 기본 상세를 만든다
        details = make_deal_details()

        # then: 담당자 id·금액·매출일이 그대로고 통화·코드 속성은 없다
        assert details.owner_user_id == OWNER_ID
        assert details.revenue_amount == RevenueAmount(150_000_000)
        assert details.revenue_date == date(2026, 6, 30)
        assert not hasattr(details, "revenue")  # Money(통화) 모델은 없다
        assert not hasattr(details, "code")  # code는 Deal의 식별자다

    def test_owner_user_id_is_kept_as_given(self) -> None:
        """담당자 사용자 id는 준 값 그대로 보관된다."""
        # when: 다른 담당자 id로 만든다
        result = make_deal_details(owner_user_id=uid("someone")).owner_user_id
        # then: 그대로다
        assert result == uid("someone")

    def test_is_comparable_by_value(self) -> None:
        """Deal 상세는 값으로 비교된다."""
        # when: 같은 값 둘과 이름만 다른 값을 만든다
        result_1 = make_deal_details()
        result_2 = make_deal_details(name="다른 딜")
        # then: 같은 값은 같고 이름이 다르면 다르다
        assert result_1 == make_deal_details()
        assert result_2 != make_deal_details()


class TestQuoteAndPoc:
    def test_enum_values_are_the_wire_values(self) -> None:
        """견적·POC 열거형의 값은 API로 나가는 값이다."""
        # when·then: 견적은 YES·NO, POC는 YES·ING·NO다
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
        """견적은 제출 여부와 날짜의 어떤 조합도 교차 검증 없이 허용한다."""
        # when: 제출 여부와 날짜 조합으로 Quote를 만든다
        quote = Quote(submitted=submitted, submitted_date=submitted_date)

        # then: 준 값 그대로 보관한다
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
        """POC는 상태와 완료일의 어떤 조합도 교차 검증 없이 허용한다."""
        # when: 상태와 완료일 조합으로 Poc를 만든다
        poc = Poc(state=state, completed_date=completed_date)

        # then: 준 값 그대로 보관한다
        assert (poc.state, poc.completed_date) == (state, completed_date)

    def test_details_keep_the_quote_and_poc(self) -> None:
        """Deal 상세는 견적과 POC를 그대로 보관한다."""
        # given: 제출한 견적과 진행 중 POC
        quote = Quote(submitted=QuoteSubmitted.YES, submitted_date=date(2026, 10, 1))
        poc = Poc(state=PocState.ING, completed_date=None)

        # when: 그 값으로 상세를 만든다
        details = make_deal_details(quote=quote, poc=poc)

        # then: 견적과 POC가 그대로다
        assert (details.quote, details.poc) == (quote, poc)


class TestBantSelection:
    def test_has_one_label_or_none_per_category(self) -> None:
        """BANT 선택은 구분마다 Label 하나 또는 없음을 가진다."""
        # given: Budget Label id
        label = BantLabelId(new_id())

        # when: Budget만 고른 선택을 만든다
        selection = make_bant(budget=label)

        # then: Budget은 그 Label이고 나머지 구분은 없음이다
        assert selection.get(BantCategory.BUDGET) == label
        others = [selection.get(c) for c in BantCategory if c is not BantCategory.BUDGET]
        assert others == [None, None, None]

    def test_with_replaces_one_category_and_keeps_the_original(self) -> None:
        """with_는 한 구분만 바꾼 새 선택을 돌려주고 원본은 그대로 둔다."""
        # given: Budget·Need를 고른 선택
        first, second = BantLabelId(new_id()), BantLabelId(new_id())
        original = make_bant(budget=first, need=second)

        # when: Need를 비운 새 선택을 만든다
        changed = original.with_(BantCategory.NEED, None)

        # then: 새 선택은 Need만 비고 원본은 그대로다
        assert changed.get(BantCategory.NEED) is None
        assert changed.get(BantCategory.BUDGET) == first
        assert original.get(BantCategory.NEED) == second  # 원본은 그대로

    def test_equal_selections_compare_equal(self) -> None:
        """같은 구성의 BANT 선택은 같다고 비교된다."""
        # given: Timeline Label id
        label = BantLabelId(new_id())

        # when: Timeline만 고른 선택을 만든다
        result = make_bant(timeline=label)
        # then: 같은 Timeline만 고른 두 선택이 같다
        assert result == BantSelection(budget=None, authority=None, need=None, timeline=label)
