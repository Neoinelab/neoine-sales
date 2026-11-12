"""User.register의 이메일·전화: 값 객체로 검증·정규화하고 빈 값은 None, 길이는 254·40."""

import pytest

from app.domain.common.errors import InvalidValueError
from tests.factories_auth import make_user

PHONE_40 = "1234567" + "-" * 33  # 40자(숫자 7개)
PHONE_41 = "1234567" + "-" * 34


def test_a_new_user_has_no_email_or_phone_by_default() -> None:
    """새 사용자는 기본으로 이메일·전화가 없다"""
    # when: 이메일·전화 없이 사용자를 만든다
    user = make_user("kim")

    # then: 둘 다 None이다
    assert (user.email, user.phone) == (None, None)


def test_register_normalizes_email_and_phone() -> None:
    """경계 안의 이메일·전화는 정규화되어 저장된다

    테스트 코드: US-015
    """
    # when: 공백·대문자가 섞인 이메일과 전화로 사용자를 만든다
    user = make_user("kim", email=" A@B.CO ", phone=" 010-1234-5678 ")

    # then: 소문자 이메일과 공백 없는 전화다
    assert user.email == "a@b.co"
    assert user.phone == "010-1234-5678"


@pytest.mark.parametrize("blank", ["", "   "])
def test_register_turns_blank_email_and_phone_into_none(blank: str) -> None:
    """빈 이메일·전화는 None으로 저장된다"""
    # when: 빈 값으로 사용자를 만든다
    user = make_user("kim", email=blank, phone=blank)

    # then: 이메일·전화가 None이다
    assert (user.email, user.phone) == (None, None)


@pytest.mark.parametrize("email", ["abc", "a@b", "a b@c.com", "@c.com"])
def test_register_rejects_an_invalid_email(email: str) -> None:
    """형식이 틀린 이메일은 거절된다

    테스트 코드: US-015
    """
    # when: 잘못된 이메일로 사용자를 만든다
    with pytest.raises(InvalidValueError):
        make_user("kim", email=email)
    # then: 입력 오류다


def test_register_rejects_an_email_over_254_chars() -> None:
    """254자를 넘는 이메일은 거절된다

    테스트 코드: US-015
    """
    # when: 254자를 넘는 이메일로 사용자를 만든다
    with pytest.raises(InvalidValueError):
        make_user("kim", email="a" * 250 + "@b.co")
    # then: 입력 오류다


@pytest.mark.parametrize("phone", ["12", "abc-defg-hij", "1234567890123456", "010*1234*5678"])
def test_register_rejects_an_invalid_phone(phone: str) -> None:
    """형식이 틀린 전화는 거절된다

    테스트 코드: US-015
    """
    # when: 잘못된 전화로 사용자를 만든다
    with pytest.raises(InvalidValueError):
        make_user("kim", phone=phone)
    # then: 입력 오류다


def test_register_accepts_a_phone_of_exactly_40_chars_and_rejects_41() -> None:
    """전화는 40자까지 허용되고 41자는 거절된다

    테스트 코드: US-015
    """
    # when: 40자와 41자 전화로 사용자를 만든다
    phone = make_user("kim", phone=PHONE_40).phone
    # then: 40자는 저장되고 41자는 입력 오류다
    assert phone == PHONE_40
    with pytest.raises(InvalidValueError):
        make_user("kim", phone=PHONE_41)
