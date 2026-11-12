"""LoginId 정규화·형식(AUTH-6, DIR-2)과 Password 값 객체(AUTH-4·7)."""

import dataclasses

import pytest

from app.domain.auth.credentials import LoginId, Password
from app.domain.common.errors import InvalidValueError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" Kim ", "kim"), ("KIM", "kim"), ("kim.lee_01-x", "kim.lee_01-x"), ("0abc", "0abc")],
)
def test_login_id_is_trimmed_and_lowercased(raw: str, expected: str) -> None:
    """로그인 아이디는 앞뒤 공백을 지우고 소문자로 정규화한다."""
    # when: 원문으로 LoginId를 만든다
    value = LoginId(raw).value

    # then: 정규화된 값이다
    assert value == expected


def test_login_ids_that_differ_only_by_case_and_spaces_are_equal() -> None:
    """대소문자와 앞뒤 공백만 다른 아이디는 같다."""
    # when: 대소문자·공백이 다른 두 LoginId를 만든다
    first = LoginId(" Kim ")
    second = LoginId("kim")
    # then: 두 LoginId가 같다
    assert first == second


def test_login_id_accepts_the_maximum_length() -> None:
    """64자 아이디는 허용한다."""
    # when: 최대 길이 아이디를 만든다
    login_id = LoginId("a" * 64)

    # then: 값이 그대로 보존된다
    assert login_id.value == "a" * 64


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "a" * 65,
        "-kim",
        ".kim",
        "_kim",
        "kim lee",
        "김영업",
        "ki\x00m",
        "ki\nm",
    ],
)
def test_login_id_rejects_bad_format(raw: str) -> None:
    """형식에 맞지 않는 로그인 아이디는 거부한다."""
    # when·then: 잘못된 형식으로 만들면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        LoginId(raw)


@pytest.mark.parametrize("char", list("*()\\,=+<>;\"#@/&|!:'`"))
def test_login_id_rejects_injection_characters(char: str) -> None:
    """LDAP 주입에 쓰이는 문자가 든 아이디는 거부한다."""
    # when·then: 특수문자가 든 아이디를 만들면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        LoginId(f"kim{char}x")


def test_password_repr_and_str_hide_the_value() -> None:
    """Password의 repr·str에는 값이 드러나지 않는다."""
    # given: 비밀번호 값 객체
    password = Password("Sup3r-secret-value")

    # when: repr·str·f-string으로 문자열을 만든다
    shown_repr = repr(password)
    shown_str = str(password)
    shown_format = f"{password!r} {password}"
    # then: 어느 문자열에도 원문이 없다
    assert "Sup3r-secret-value" not in shown_repr
    assert "Sup3r-secret-value" not in shown_str
    assert "Sup3r-secret-value" not in shown_format


def test_password_reveal_returns_the_original_without_stripping() -> None:
    """reveal은 공백을 지우지 않고 원문을 돌려준다."""
    # when: 공백이 든 비밀번호를 reveal한다
    revealed = Password("  pw with spaces  ").reveal()

    # then: 원문 그대로다
    assert revealed == "  pw with spaces  "


def test_password_is_frozen() -> None:
    """Password는 불변이다."""
    # given: 비밀번호 값 객체
    password = Password("pw")

    # when·then: 값을 바꾸려 하면 FrozenInstanceError가 난다
    with pytest.raises(dataclasses.FrozenInstanceError):
        password.value = "other"  # type: ignore[misc]


def test_password_accepts_the_maximum_length() -> None:
    """256자 비밀번호는 허용한다."""
    # when: 최대 길이 비밀번호를 만든다
    revealed = Password("p" * 256).reveal()

    # then: 길이가 그대로 보존된다
    assert len(revealed) == 256


@pytest.mark.parametrize("raw", ["", " ", "   \t ", "pw\x00x", "\x00", "p" * 257])
def test_password_rejects_empty_whitespace_nul_and_too_long(raw: str) -> None:
    """빈 값·공백뿐·NUL 포함·257자 비밀번호는 거부한다."""
    # when·then: 잘못된 비밀번호를 만들면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        Password(raw)


def test_password_error_message_does_not_contain_the_value() -> None:
    """거부 오류 메시지에는 비밀번호 값이 들어 있지 않다."""
    # given: 길이를 넘긴 비밀번호 원문
    raw = "x" * 257

    # when: 만들어 거부된다
    with pytest.raises(InvalidValueError) as caught:
        Password(raw)

    # then: 오류의 문자열과 repr에 원문이 없다
    assert raw not in str(caught.value)
    assert raw not in repr(caught.value)
