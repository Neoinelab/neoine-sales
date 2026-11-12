"""로컬 비밀번호 정책: 8자 이상, 아이디와 같으면 거부, 조합 규칙 없음."""

import pytest

from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import WeakPasswordError
from app.domain.auth.password_policy import PASSWORD_MIN, ensure_acceptable_password


def test_minimum_length_is_eight() -> None:
    """비밀번호 최소 길이는 8자다."""
    # when·then: PASSWORD_MIN이 8이다
    assert PASSWORD_MIN == 8


def test_password_of_seven_chars_is_rejected() -> None:
    """7자 비밀번호는 WeakPasswordError로 거절된다."""
    # when·then: 7자 비밀번호를 검사하면 WeakPasswordError다
    with pytest.raises(WeakPasswordError):
        ensure_acceptable_password(Password("abcdefg"), LoginId("kim"))


def test_password_of_eight_chars_is_accepted() -> None:
    """8자 비밀번호는 허용된다."""
    # when·then: 8자 비밀번호를 검사해도 오류가 없다
    ensure_acceptable_password(Password("abcdefgh"), LoginId("kim"))


def test_digits_only_or_letters_only_passwords_need_no_character_mix() -> None:
    """숫자만 또는 문자만으로 된 비밀번호도 조합 규칙 없이 허용된다."""
    # when·then: 숫자만·문자만 8자 비밀번호를 검사해도 오류가 없다
    ensure_acceptable_password(Password("12345678"), LoginId("kim"))
    ensure_acceptable_password(Password("aaaaaaaa"), LoginId("kim"))


def test_password_equal_to_login_id_ignoring_case_is_rejected() -> None:
    """대소문자만 다르고 아이디와 같은 비밀번호는 거절된다."""
    # when·then: 아이디와 대소문자만 다른 비밀번호는 WeakPasswordError다
    with pytest.raises(WeakPasswordError):
        ensure_acceptable_password(Password("Kim.Lee1"), LoginId("kim.lee1"))


def test_password_equal_to_login_id_after_trimming_is_rejected() -> None:
    """앞뒤 공백을 자르면 아이디와 같은 비밀번호는 거절된다."""
    # when·then: 공백을 덧붙인 아이디 비밀번호는 WeakPasswordError다
    with pytest.raises(WeakPasswordError):
        ensure_acceptable_password(Password("  kim.lee1  "), LoginId("kim.lee1"))


def test_password_that_only_contains_the_login_id_is_accepted() -> None:
    """아이디를 포함할 뿐 같지는 않은 비밀번호는 허용된다."""
    # when·then: 아이디를 포함한 8자 비밀번호를 검사해도 오류가 없다
    ensure_acceptable_password(Password("KIM12345"), LoginId("kim"))


def test_a_long_password_up_to_the_domain_maximum_is_accepted() -> None:
    """도메인 최대 길이(256자)까지의 비밀번호는 허용된다."""
    # when·then: 256자 비밀번호를 검사해도 오류가 없다
    ensure_acceptable_password(Password("a" * 256), LoginId("kim"))


def test_a_weak_password_error_is_an_invalid_value_error_so_it_maps_to_422() -> None:
    """WeakPasswordError는 InvalidValueError이므로 422로 매핑된다."""
    from app.domain.common.errors import InvalidValueError  # noqa: PLC0415

    # when·then: 짧은 비밀번호를 검사하면 InvalidValueError로 잡힌다
    with pytest.raises(InvalidValueError):
        ensure_acceptable_password(Password("short"), LoginId("kim"))
