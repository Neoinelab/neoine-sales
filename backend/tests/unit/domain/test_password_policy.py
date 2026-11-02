"""로컬 비밀번호 정책 (AC-4·6·7·11, Q3): 8자 이상, 아이디와 같으면 거부, 조합 규칙 없음."""

import pytest

from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import WeakPasswordError
from app.domain.auth.password_policy import PASSWORD_MIN, ensure_acceptable_password


def test_minimum_length_is_eight() -> None:
    assert PASSWORD_MIN == 8


def test_password_of_seven_chars_is_rejected() -> None:
    with pytest.raises(WeakPasswordError):
        ensure_acceptable_password(Password("abcdefg"), LoginId("kim"))


def test_password_of_eight_chars_is_accepted() -> None:
    ensure_acceptable_password(Password("abcdefgh"), LoginId("kim"))


def test_digits_only_or_letters_only_passwords_need_no_character_mix() -> None:
    ensure_acceptable_password(Password("12345678"), LoginId("kim"))
    ensure_acceptable_password(Password("aaaaaaaa"), LoginId("kim"))


def test_password_equal_to_login_id_ignoring_case_is_rejected() -> None:
    with pytest.raises(WeakPasswordError):
        ensure_acceptable_password(Password("Kim.Lee1"), LoginId("kim.lee1"))


def test_password_equal_to_login_id_after_trimming_is_rejected() -> None:
    with pytest.raises(WeakPasswordError):
        ensure_acceptable_password(Password("  kim.lee1  "), LoginId("kim.lee1"))


def test_password_that_only_contains_the_login_id_is_accepted() -> None:
    ensure_acceptable_password(Password("KIM12345"), LoginId("kim"))


def test_a_long_password_up_to_the_domain_maximum_is_accepted() -> None:
    ensure_acceptable_password(Password("a" * 256), LoginId("kim"))


def test_a_weak_password_error_is_an_invalid_value_error_so_it_maps_to_422() -> None:
    from app.domain.common.errors import InvalidValueError  # noqa: PLC0415

    with pytest.raises(InvalidValueError):
        ensure_acceptable_password(Password("short"), LoginId("kim"))
