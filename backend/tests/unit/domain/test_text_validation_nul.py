"""공용 텍스트 검증: NUL 문자는 PostgreSQL이 거부하므로 도메인에서 InvalidValueError로 막는다."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text, required_text


@pytest.mark.parametrize("value", ["a\x00b", "\x00", "abc\x00", "\x00abc", " a\x00 "])
def test_required_text_rejects_nul_character(value: str) -> None:
    with pytest.raises(InvalidValueError):
        required_text(value, "이름", max_length=50)


@pytest.mark.parametrize("value", ["a\x00b", "abc\x00", "\x00abc"])
def test_optional_text_rejects_nul_character(value: str) -> None:
    with pytest.raises(InvalidValueError):
        optional_text(value, "이름", max_length=50)


def test_nul_error_message_names_the_field() -> None:
    with pytest.raises(InvalidValueError, match="검색어"):
        required_text("a\x00b", "검색어", max_length=50)


@pytest.mark.parametrize("value", ["a\x01b", "a\x1fb", "a\x7fb", "a\tb", "a\nb"])
def test_other_control_characters_are_still_accepted(value: str) -> None:
    assert required_text(value, "이름", max_length=50) == value
    assert optional_text(value, "이름", max_length=50) == value


def test_normal_and_korean_text_is_unchanged_apart_from_strip() -> None:
    assert required_text("  네오인 Co. ", "이름", max_length=50) == "네오인 Co."
    assert optional_text("  한글  ", "이름", max_length=50) == "한글"


def test_optional_text_keeps_none_and_blank_as_none() -> None:
    assert optional_text(None, "이름", max_length=50) is None
    assert optional_text("   ", "이름", max_length=50) is None
