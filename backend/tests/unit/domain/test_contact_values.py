"""연락처 값 객체(ContactKind, ContactDetails): 필수값, 공백 거절, 직급 정리, 길이 한도(AC-19).

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
        assert [kind.value for kind in ContactKind] == ["customer", "partner"]

    def test_is_built_from_its_text_value(self) -> None:
        assert ContactKind("customer") is ContactKind.CUSTOMER
        assert ContactKind("partner") is ContactKind.PARTNER

    def test_unknown_value_is_rejected(self) -> None:
        with pytest.raises(ValueError):  # noqa: PT011 - StrEnum 변환 오류
            ContactKind("supplier")


class TestContactDetails:
    def test_keeps_all_given_values(self) -> None:
        details = make_contact_details()

        assert details.company == "네오인"
        assert details.name == "김철수"
        assert details.title == "팀장"
        assert details.email == Email("kim@neoine.example")
        assert details.phone == PhoneNumber("010-1234-5678")

    def test_only_company_and_name_are_required(self) -> None:
        details = ContactDetails(
            company="네오인", name="김철수", title=None, email=None, phone=None
        )

        assert (details.title, details.email, details.phone) == (None, None, None)

    @pytest.mark.parametrize(
        ("field", "message"),
        [("company", "회사명을 입력하세요."), ("name", "담당자명을 입력하세요.")],
    )
    def test_empty_company_or_name_is_rejected_with_its_message(
        self, field: str, message: str
    ) -> None:
        with pytest.raises(InvalidValueError) as error:
            make_contact_details(**only(field, ""))

        assert str(error.value) == message

    @pytest.mark.parametrize("field", ["company", "name"])
    @pytest.mark.parametrize("value", WHITESPACE_VALUES)
    def test_any_whitespace_in_company_or_name_is_rejected_not_stripped(
        self, field: str, value: str
    ) -> None:
        with pytest.raises(InvalidValueError) as error:
            make_contact_details(**only(field, value))

        assert str(error.value) == WHITESPACE_MESSAGE

    @pytest.mark.parametrize("field", ["company", "name", "title"])
    def test_nul_character_is_rejected(self, field: str) -> None:
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
        assert make_contact_details(title=raw).title == expected

    @pytest.mark.parametrize(
        ("field", "max_length"), [("company", 200), ("name", 100), ("title", 100)]
    )
    def test_maximum_text_lengths_are_enforced(self, field: str, max_length: int) -> None:
        assert (
            getattr(make_contact_details(**only(field, "a" * max_length)), field)
            == "a" * max_length
        )
        with pytest.raises(InvalidValueError):
            make_contact_details(**only(field, "a" * (max_length + 1)))

    def test_title_length_limit_applies_after_trimming(self) -> None:
        assert make_contact_details(title=f"  {'a' * 100}  ").title == "a" * 100

    def test_details_are_immutable(self) -> None:
        details = make_contact_details()

        with pytest.raises(AttributeError):
            details.company = "다른회사"  # type: ignore[misc, unused-ignore]
