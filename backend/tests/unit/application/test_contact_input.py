"""ContactInput.to_details(): 원문 입력을 검증해 ContactDetails로 바꾼다.

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
    """유효한 원문 입력은 값 객체를 가진 ContactDetails가 되고 이메일은 소문자가 된다.

    테스트 코드: CT-003
    """
    # when: 상세 값으로 변환한다 (전제: 대문자가 섞인 이메일을 가진 입력)
    details = make_contact_input(email="Kim@Neoine.Example").to_details()

    # then: 값 객체로 바뀌고 이메일은 소문자다

    assert details.company == "네오인"
    assert details.name == "김철수"
    assert details.title == "팀장"
    assert details.email == Email("kim@neoine.example")
    assert details.phone == PhoneNumber("010-1234-5678")


@pytest.mark.parametrize(("field", "value"), WHITESPACE_PARAMS)
def test_any_whitespace_in_company_name_email_or_phone_is_rejected(field: str, value: str) -> None:
    """회사명·담당자명·이메일·전화에 공백 문자가 하나라도 있으면 잘라 내지 않고 거절한다.

    테스트 코드: CT-006
    """
    # when: 상세 값으로 변환한다 (전제: 한 칸에만 공백(앞·뒤·가운데·탭·줄바꿈·전각)이 든 입력)
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(**only(field, value)).to_details()

    # then: 공백 오류 문구로 거절된다
    assert str(error.value) == WHITESPACE_MESSAGE


@pytest.mark.parametrize("field", ["email", "phone"])
def test_whitespace_only_email_or_phone_is_rejected_not_treated_as_empty(field: str) -> None:
    """공백뿐인 이메일·전화는 없는 값이 아니라 공백 오류다.

    테스트 코드: CT-007
    """
    # when: 상세 값으로 변환한다 (전제: 공백뿐인 이메일 또는 전화)
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(**only(field, "   ")).to_details()

    # then: 공백 오류 문구다
    assert str(error.value) == WHITESPACE_MESSAGE


@pytest.mark.parametrize("field", ["email", "phone", "title"])
def test_empty_string_email_phone_or_title_becomes_none(field: str) -> None:
    """이메일·전화·직급의 빈 문자열은 없는 값(None)이 된다.

    테스트 코드: CT-004, CT-005
    """
    # when: 상세 값으로 변환한다 (전제: 빈 문자열인 선택 칸)
    details = make_contact_input(**only(field, "")).to_details()

    # then: 값이 없다
    assert getattr(details, field) is None


@pytest.mark.parametrize("field", ["email", "phone", "title"])
def test_missing_email_phone_or_title_stays_none(field: str) -> None:
    """이메일·전화·직급이 null이면 없는 값으로 남는다.

    테스트 코드: CT-002
    """
    # when: 상세 값으로 변환한다 (전제: 선택 칸이 null인 입력)
    details = make_contact_input(**only(field, None)).to_details()

    # then: 값이 없다
    assert getattr(details, field) is None


@pytest.mark.parametrize(
    ("field", "message"),
    [("company", "회사명을 입력하세요."), ("name", "담당자명을 입력하세요.")],
)
def test_empty_company_or_name_is_rejected_with_its_message(field: str, message: str) -> None:
    """회사명·담당자명이 비어 있으면 각자의 문구로 거절한다.

    테스트 코드: CT-008
    """
    # when: 상세 값으로 변환한다 (전제: 빈 회사명 또는 빈 담당자명)
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(**only(field, "")).to_details()

    # then: 칸마다 정해진 문구다
    assert str(error.value) == message


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "a@b", "@neoine.example", "kim@", "kim@@neoine.example", "kim@.example"],
)
def test_malformed_email_is_rejected_with_the_format_message(email: str) -> None:
    """형식이 틀린 이메일은 형식 오류 문구로 거절한다.

    테스트 코드: CT-009
    """
    # when: 상세 값으로 변환한다 (전제: 형식이 틀린 이메일)
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(email=email).to_details()

    # then: 이메일 형식 문구다
    assert str(error.value) == EMAIL_MESSAGE


def test_email_over_254_characters_is_rejected_and_254_is_accepted() -> None:
    """소문자로 바꾼 이메일이 254자를 넘으면 거절하고 254자까지는 받는다.

    테스트 코드: CT-009
    """
    # given: 254자와 255자 이메일
    at_limit = "a" * 242 + "@neoine.test"  # 254자
    over_limit = "a" * 243 + "@neoine.test"  # 255자

    # when: 각각 변환한다
    accepted = make_contact_input(email=at_limit).to_details()
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(email=over_limit).to_details()

    # then: 254자는 저장 값이 되고 255자는 형식 오류다
    assert accepted.email == Email(at_limit)
    assert str(error.value) == EMAIL_MESSAGE


@pytest.mark.parametrize("phone", ["abc", "12-34", "1234567890123456", "010-1234-567x", "++"])
def test_malformed_phone_is_rejected_with_the_format_message(phone: str) -> None:
    """문자가 섞였거나 숫자 7~15개를 벗어난 전화는 형식 오류 문구로 거절한다.

    테스트 코드: CT-010
    """
    # when: 상세 값으로 변환한다 (전제: 형식이 틀린 전화)
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(phone=phone).to_details()

    # then: 전화 형식 문구를 포함한다
    assert PHONE_MESSAGE in str(error.value)


@pytest.mark.parametrize(
    "phone", ["010-1234-5678", "+82-10-1234-5678", "(02)123-4567", "0212345678"]
)
def test_common_phone_formats_are_accepted(phone: str) -> None:
    """흔한 전화 형식은 입력 표기 그대로 받는다.

    테스트 코드: CT-010
    """
    # when: 상세 값으로 변환한다 (전제: 흔한 전화 형식)
    actual = make_contact_input(phone=phone).to_details().phone
    # then: 입력 표기 그대로 전화가 된다
    assert actual == PhoneNumber(phone)


def test_title_is_trimmed_but_keeps_inner_spaces() -> None:
    """직급은 앞뒤 공백만 지우고 내부 공백은 두며 공백뿐이면 없는 값이다.

    테스트 코드: CT-004
    """
    # when: 각각 상세 값으로 변환한다 (전제: 앞뒤 공백이 있는 직급과 공백뿐인 직급)
    title = make_contact_input(title="  수석 과장  ").to_details().title
    # then: 앞뒤만 지워지고, 공백뿐이면 None이다
    assert title == "수석 과장"
    assert make_contact_input(title="   ").to_details().title is None


@pytest.mark.parametrize("field", ["company", "name", "title", "email", "phone"])
def test_nul_character_is_rejected(field: str) -> None:
    """NUL 문자가 든 입력은 어느 칸이든 거절한다.

    테스트 코드: CT-011
    """
    # when·then: 상세 값으로 변환한다 → 입력값 오류다 (전제: NUL 문자가 든 한 칸)
    with pytest.raises(InvalidValueError):
        make_contact_input(**only(field, "a\x00b")).to_details()


def test_the_nul_message_names_the_problem_for_text_fields() -> None:
    """NUL 오류 문구는 NUL 문자를 쓸 수 없다는 사실을 알리고 DB 문구가 없다.

    테스트 코드: CT-011
    """
    # when·then: 상세 값으로 변환한다 → 문구가 NUL을 가리킨다 (전제: NUL이 든 회사명)
    with pytest.raises(InvalidValueError, match="NUL"):
        make_contact_input(company="a\x00b").to_details()


def test_values_at_the_length_limits_are_accepted() -> None:
    """회사명 200자·담당자명 100자·직급 100자는 받는다.

    테스트 코드: CT-012
    """
    # when: 상세 값으로 변환한다 (전제: 한도 길이의 회사명·담당자명·직급)
    details = make_contact_input(company="a" * 200, name="b" * 100, title="c" * 100).to_details()

    # then: 잘리지 않고 그대로다
    assert (details.company, details.name, details.title) == ("a" * 200, "b" * 100, "c" * 100)


@pytest.mark.parametrize(("field", "limit"), [("company", 200), ("name", 100), ("title", 100)])
def test_values_over_the_length_limits_are_rejected(field: str, limit: int) -> None:
    """회사명 201자·담당자명 101자·직급 101자는 길이 오류 문구로 거절한다.

    테스트 코드: CT-013
    """
    # when: 상세 값으로 변환한다 (전제: 한도를 1자 넘는 값)
    with pytest.raises(InvalidValueError) as error:
        make_contact_input(**only(field, "a" * (limit + 1))).to_details()

    # then: 칸 이름과 한도를 담은 길이 오류다
    assert f"{limit}자를 넘을 수 없습니다" in str(error.value)
