"""연락처 값 객체(ContactKind, ContactDetails): 필수값, 공백 거절, 직급 정리, 길이 한도.

이메일·전화의 공백/형식 규칙은 원문을 받는 `ContactInput.to_details()`가 맡는다
(tests/unit/application/test_contact_input.py).
"""

import pytest

from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import InvalidValueError
from app.domain.contact.values import ContactDetails, ContactKind
from tests.factories_contact import make_contact_details, only

WHITESPACE_MESSAGE = "공백은 입력할 수 없습니다."
# 공백 문자가 하나라도 있는 값: 앞·뒤·중간·탭·줄바꿈·전각 공백·공백만
WHITESPACE_VALUES = ["x ", " x", "x y", "x\ty", "x\ny", "x　y", "　x", "   "]


class TestContactKind:
    def test_has_customer_then_partner(self) -> None:
        """연락처 종류는 customer, partner 순서의 두 값이다."""
        # when: 값을 순서대로 나열한다
        values = [kind.value for kind in ContactKind]
        # then: customer, partner다
        assert values == ["customer", "partner"]

    def test_is_built_from_its_text_value(self) -> None:
        """문자열 값으로 연락처 종류를 만들 수 있다."""
        # when: customer·partner 문자열로 만든다
        result_1 = ContactKind("customer")
        result_2 = ContactKind("partner")
        # then: 각각 CUSTOMER·PARTNER 종류가 된다
        assert result_1 is ContactKind.CUSTOMER
        assert result_2 is ContactKind.PARTNER

    def test_unknown_value_is_rejected(self) -> None:
        """모르는 종류 문자열은 거절된다."""
        # when·then: supplier로 만들면 ValueError다
        with pytest.raises(ValueError):  # noqa: PT011 - StrEnum 변환 오류
            ContactKind("supplier")


class TestContactDetails:
    def test_keeps_all_given_values(self) -> None:
        """연락처 상세는 받은 값을 그대로 보관한다."""
        # when: 기본 값으로 상세를 만든다
        details = make_contact_details()

        # then: 회사·이름·직급·이메일·전화가 그대로다
        assert details.company == "네오인"
        assert details.name == "김철수"
        assert details.title == "팀장"
        assert details.email == Email("kim@neoine.example")
        assert details.phone == PhoneNumber("010-1234-5678")

    def test_only_company_and_name_are_required(self) -> None:
        """회사와 이름만 필수이고 나머지는 비워 둘 수 있다."""
        # when: 회사와 이름만으로 상세를 만든다
        details = ContactDetails(
            company="네오인", name="김철수", title=None, email=None, phone=None
        )

        # then: 직급·이메일·전화는 None이다
        assert (details.title, details.email, details.phone) == (None, None, None)

    @pytest.mark.parametrize(
        ("field", "message"),
        [("company", "회사명을 입력하세요."), ("name", "담당자명을 입력하세요.")],
    )
    def test_empty_company_or_name_is_rejected_with_its_message(
        self, field: str, message: str
    ) -> None:
        """빈 회사 또는 이름은 필드별 문구와 함께 거절된다."""
        # when·then: 빈 값으로 만들면 InvalidValueError다
        with pytest.raises(InvalidValueError) as error:
            make_contact_details(**only(field, ""))

        # then: 문구가 필드별 안내다
        assert str(error.value) == message

    @pytest.mark.parametrize("field", ["company", "name"])
    @pytest.mark.parametrize("value", WHITESPACE_VALUES)
    def test_any_whitespace_in_company_or_name_is_rejected_not_stripped(
        self, field: str, value: str
    ) -> None:
        """회사·이름에 공백이 하나라도 있으면 잘라 내지 않고 거절한다."""
        # when·then: 공백이 든 값으로 만들면 InvalidValueError다
        with pytest.raises(InvalidValueError) as error:
            make_contact_details(**only(field, value))

        # then: 문구가 공백 불가 안내다
        assert str(error.value) == WHITESPACE_MESSAGE

    @pytest.mark.parametrize("field", ["company", "name", "title"])
    def test_nul_character_is_rejected(self, field: str) -> None:
        """회사·이름·직급에 NUL 문자가 있으면 거절된다."""
        # when·then: NUL이 든 값으로 만들면 NUL 안내 InvalidValueError다
        with pytest.raises(InvalidValueError, match="NUL"):
            make_contact_details(**only(field, "a\x00b"))

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("  팀장  ", "팀장"),
            ("수석 과장", "수석 과장"),  # 내부 공백은 직급에서 허용된다
            ("\t이사\t", "이사"),
            ("", None),
            ("   ", None),
            (None, None),
        ],
    )
    def test_title_is_trimmed_and_blank_becomes_none(
        self, raw: str | None, expected: str | None
    ) -> None:
        """직급은 앞뒤 공백을 자르고 빈 값은 None이 된다."""
        # when: 직급 원문으로 만든다
        result = make_contact_details(title=raw).title
        # then: 정리된 값(또는 None)이 된다
        assert result == expected

    @pytest.mark.parametrize(
        ("field", "max_length"), [("company", 200), ("name", 100), ("title", 100)]
    )
    def test_maximum_text_lengths_are_enforced(self, field: str, max_length: int) -> None:
        """회사 200자, 이름·직급 100자까지만 허용한다."""
        # when: 최대 길이 값으로 만든다
        result = getattr(make_contact_details(**only(field, "a" * max_length)), field)
        # then: 그대로 보관한다
        assert result == "a" * max_length
        # when·then: 최대 길이보다 1자 길면 InvalidValueError다
        with pytest.raises(InvalidValueError):
            make_contact_details(**only(field, "a" * (max_length + 1)))

    def test_title_length_limit_applies_after_trimming(self) -> None:
        """직급 길이 제한은 앞뒤 공백을 자른 뒤 적용된다."""
        # when: 공백 포함 104자지만 자른다
        result = make_contact_details(title=f"  {'a' * 100}  ").title
        # then: 100자인 직급은 허용된다
        assert result == "a" * 100

    def test_details_are_immutable(self) -> None:
        """연락처 상세는 만든 뒤 바꿀 수 없다."""
        # given: 기본 연락처 상세
        details = make_contact_details()

        # when·then: 회사를 바꾸려 하면 AttributeError다
        with pytest.raises(AttributeError):
            details.company = "다른회사"  # type: ignore[misc, unused-ignore]
