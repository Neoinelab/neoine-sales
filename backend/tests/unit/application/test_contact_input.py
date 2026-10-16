"""ContactInput.to_details(): 원문 입력을 검증해 ContactDetails로 바꾼다(AC-19).

공백 문자가 하나라도 있으면 strip하지 않고 거절하며(회사명·담당자명·이메일·전화), 직급은 앞뒤 공백만
제거한다. 이메일·전화의 빈 문자열("")은 None이다. 프런트 `validateContactInput`과 같은 규칙이다.
"""

import pytest

from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import InvalidValueError
from tests.factories_contact import make_contact_input, only

WHITESPACE_MESSAGE = "공백은 입력할 수 없습니다."
EMAIL_MESSAGE = "이메일 형식이 올바르지 않습니다."
PHONE_MESSAGE = "전화번호 형식이 올바르지 않습니다."

# 필드별로 공백 하나만 섞은 값(앞·뒤·중간·탭·줄바꿈·전각 공백)
WHITESPACE_CASES = {
    "company": ["네오 인", " 네오인", "네오인 ", "네오\t인", "네오\n인", "네오　인", "　네오인"],
    "name": ["김 철수", " 김철수", "김철수 ", "김\t철수", "김\n철수", "김　철수", "　김철수"],
    "email": [
        "kim @neoine.example",
        " kim@neoine.example",
        "kim@neoine.example ",
        "kim@neoine.example\t",
        "kim@neo　ine.example",
    ],
    "phone": [
        "010 1234 5678",
        " 010-1234-5678",
        "010-1234-5678 ",
        "010\t1234\n5678",
        "010-1234　5678",
    ],
}
WHITESPACE_PARAMS = [
    (field, value) for field, values in WHITESPACE_CASES.items() for value in values
]


def test_valid_input_becomes_details_with_value_objects() -> None:
    details = make_contact_input(email="Kim@Neoine.Example").to_details()

    assert details.company == "네오인"
    assert details.name == "김철수"
    assert details.title == "팀장"
    assert details.email == Email("kim@neoine.example")
    assert details.phone == PhoneNumber("010-1234-5678")


@pytest.mark.parametrize(("field", "value"), WHITESPACE_PARAMS)
def test_any_whitespace_in_company_name_email_or_phone_is_rejected(field: str, value: str) -> None:
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(**only(field, value)).to_details()

    assert str(error.value) == WHITESPACE_MESSAGE


@pytest.mark.parametrize("field", ["email", "phone"])
def test_whitespace_only_email_or_phone_is_rejected_not_treated_as_empty(field: str) -> None:
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(**only(field, "   ")).to_details()

    assert str(error.value) == WHITESPACE_MESSAGE


@pytest.mark.parametrize("field", ["email", "phone", "title"])
def test_empty_string_email_phone_or_title_becomes_none(field: str) -> None:
    details = make_contact_input(**only(field, "")).to_details()

    assert getattr(details, field) is None


@pytest.mark.parametrize("field", ["email", "phone", "title"])
def test_missing_email_phone_or_title_stays_none(field: str) -> None:
    details = make_contact_input(**only(field, None)).to_details()

    assert getattr(details, field) is None


@pytest.mark.parametrize(
    ("field", "message"),
    [("company", "회사명을 입력하세요."), ("name", "담당자명을 입력하세요.")],
)
def test_empty_company_or_name_is_rejected_with_its_message(field: str, message: str) -> None:
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(**only(field, "")).to_details()

    assert str(error.value) == message


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "a@b", "@neoine.example", "kim@", "kim@@neoine.example", "kim@.example"],
)
def test_malformed_email_is_rejected_with_the_format_message(email: str) -> None:
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(email=email).to_details()

    assert str(error.value) == EMAIL_MESSAGE


@pytest.mark.parametrize("phone", ["abc", "12-34", "1234567890123456", "010-1234-567x", "++"])
def test_malformed_phone_is_rejected_with_the_format_message(phone: str) -> None:
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(phone=phone).to_details()

    assert PHONE_MESSAGE in str(error.value)


@pytest.mark.parametrize(
    "phone", ["010-1234-5678", "+82-10-1234-5678", "(02)123-4567", "0212345678"]
)
def test_common_phone_formats_are_accepted(phone: str) -> None:
    assert make_contact_input(phone=phone).to_details().phone == PhoneNumber(phone)


def test_title_is_trimmed_but_keeps_inner_spaces() -> None:
    assert make_contact_input(title="  수석 과장  ").to_details().title == "수석 과장"
    assert make_contact_input(title="   ").to_details().title is None


@pytest.mark.parametrize("field", ["company", "name", "title", "email", "phone"])
def test_nul_character_is_rejected(field: str) -> None:
    with pytest.raises(InvalidValueError):
        make_contact_input(**only(field, "a\x00b")).to_details()


def test_the_nul_message_names_the_problem_for_text_fields() -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        make_contact_input(company="a\x00b").to_details()


def test_values_over_the_length_limits_are_rejected() -> None:
    assert make_contact_input(company="a" * 200).to_details().company == "a" * 200
    for field, limit in (("company", 200), ("name", 100), ("title", 100)):
        with pytest.raises(InvalidValueError):
            make_contact_input(**only(field, "a" * (limit + 1))).to_details()
