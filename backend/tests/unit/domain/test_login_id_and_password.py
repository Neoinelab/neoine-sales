"""T-D2~D5: LoginId 정규화·형식(AUTH-6, DIR-2)과 Password 값 객체(AUTH-4·7)."""

import dataclasses

import pytest

from app.domain.auth.credentials import LoginId, Password
from app.domain.common.errors import InvalidValueError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" Kim ", "kim"), ("KIM", "kim"), ("kim.lee_01-x", "kim.lee_01-x"), ("0abc", "0abc")],
)
def test_login_id_is_trimmed_and_lowercased(raw: str, expected: str) -> None:
    assert LoginId(raw).value == expected


def test_login_ids_that_differ_only_by_case_and_spaces_are_equal() -> None:
    assert LoginId(" Kim ") == LoginId("kim")


def test_login_id_accepts_the_maximum_length() -> None:
    assert LoginId("a" * 64).value == "a" * 64


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
    with pytest.raises(InvalidValueError):
        LoginId(raw)


@pytest.mark.parametrize("char", list("*()\\,=+<>;\"#@/&|!:'`"))
def test_login_id_rejects_injection_characters(char: str) -> None:
    with pytest.raises(InvalidValueError):
        LoginId(f"kim{char}x")


def test_password_repr_and_str_hide_the_value() -> None:
    password = Password("Sup3r-secret-value")

    assert "Sup3r-secret-value" not in repr(password)
    assert "Sup3r-secret-value" not in str(password)
    assert "Sup3r-secret-value" not in f"{password!r} {password}"


def test_password_reveal_returns_the_original_without_stripping() -> None:
    assert Password("  pw with spaces  ").reveal() == "  pw with spaces  "


def test_password_is_frozen() -> None:
    password = Password("pw")

    with pytest.raises(dataclasses.FrozenInstanceError):
        password.value = "other"  # type: ignore[misc]


def test_password_accepts_the_maximum_length() -> None:
    assert len(Password("p" * 256).reveal()) == 256


@pytest.mark.parametrize("raw", ["", " ", "   \t ", "pw\x00x", "\x00", "p" * 257])
def test_password_rejects_empty_whitespace_nul_and_too_long(raw: str) -> None:
    with pytest.raises(InvalidValueError):
        Password(raw)


def test_password_error_message_does_not_contain_the_value() -> None:
    raw = "x" * 257

    with pytest.raises(InvalidValueError) as caught:
        Password(raw)

    assert raw not in str(caught.value)
    assert raw not in repr(caught.value)
