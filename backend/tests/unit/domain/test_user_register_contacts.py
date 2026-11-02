"""User.register의 이메일·전화 (AC-6): 값 객체로 검증·정규화하고 빈 값은 None, 길이는 254·40."""

import pytest

from app.domain.common.errors import InvalidValueError
from tests.factories_auth import make_user

PHONE_40 = "1234567" + "-" * 33  # 40자(숫자 7개)
PHONE_41 = "1234567" + "-" * 34


def test_a_new_user_has_no_email_or_phone_by_default() -> None:
    user = make_user("kim")

    assert (user.email, user.phone) == (None, None)


def test_register_normalizes_email_and_phone() -> None:
    user = make_user("kim", email=" A@B.CO ", phone=" 010-1234-5678 ")

    assert user.email == "a@b.co"
    assert user.phone == "010-1234-5678"


@pytest.mark.parametrize("blank", ["", "   "])
def test_register_turns_blank_email_and_phone_into_none(blank: str) -> None:
    user = make_user("kim", email=blank, phone=blank)

    assert (user.email, user.phone) == (None, None)


@pytest.mark.parametrize("email", ["abc", "a@b", "a b@c.com", "@c.com"])
def test_register_rejects_an_invalid_email(email: str) -> None:
    with pytest.raises(InvalidValueError):
        make_user("kim", email=email)


def test_register_rejects_an_email_over_254_chars() -> None:
    with pytest.raises(InvalidValueError):
        make_user("kim", email="a" * 250 + "@b.co")


@pytest.mark.parametrize("phone", ["12", "abc-defg-hij", "1234567890123456", "010*1234*5678"])
def test_register_rejects_an_invalid_phone(phone: str) -> None:
    with pytest.raises(InvalidValueError):
        make_user("kim", phone=phone)


def test_register_accepts_a_phone_of_exactly_40_chars_and_rejects_41() -> None:
    assert make_user("kim", phone=PHONE_40).phone == PHONE_40
    with pytest.raises(InvalidValueError):
        make_user("kim", phone=PHONE_41)
