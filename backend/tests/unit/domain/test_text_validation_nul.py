"""공용 텍스트 검증: NUL 문자는 PostgreSQL이 거부하므로 도메인에서 InvalidValueError로 막는다."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text, required_text


@pytest.mark.parametrize("value", ["a\x00b", "\x00", "abc\x00", "\x00abc", " a\x00 "])
def test_required_text_rejects_nul_character(value: str) -> None:
    """필수 텍스트는 NUL 문자가 있으면 거부한다."""
    # when·then: NUL이 든 값을 검증하면 값 오류다
    with pytest.raises(InvalidValueError):
        required_text(value, "이름", max_length=50)


@pytest.mark.parametrize("value", ["a\x00b", "abc\x00", "\x00abc"])
def test_optional_text_rejects_nul_character(value: str) -> None:
    """선택 텍스트도 NUL 문자가 있으면 거부한다."""
    # when·then: NUL이 든 값을 검증하면 값 오류다
    with pytest.raises(InvalidValueError):
        optional_text(value, "이름", max_length=50)


def test_nul_error_message_names_the_field() -> None:
    """NUL 오류 메시지에는 필드 이름이 들어간다."""
    # when·then: 필드명을 검색어로 검증하면 메시지에 검색어가 있다
    with pytest.raises(InvalidValueError, match="검색어"):
        required_text("a\x00b", "검색어", max_length=50)


@pytest.mark.parametrize("value", ["a\x01b", "a\x1fb", "a\x7fb", "a\tb", "a\nb"])
def test_other_control_characters_are_still_accepted(value: str) -> None:
    """NUL 외의 제어 문자는 계속 허용한다."""
    # when: NUL이 아닌 제어 문자가 든 텍스트를 검증한다
    result = required_text(value, "이름", max_length=50)
    # then: 값이 그대로 통과한다
    assert result == value
    assert optional_text(value, "이름", max_length=50) == value


def test_normal_and_korean_text_is_unchanged_apart_from_strip() -> None:
    """일반·한글 텍스트는 앞뒤 공백 제거 외에는 바뀌지 않는다."""
    # when: 앞뒤에 공백이 있는 텍스트를 검증한다
    result = required_text("  네오인 Co. ", "이름", max_length=50)
    # then: 앞뒤 공백만 제거된 값을 돌려준다
    assert result == "네오인 Co."
    assert optional_text("  한글  ", "이름", max_length=50) == "한글"


def test_optional_text_keeps_none_and_blank_as_none() -> None:
    """None과 공백뿐인 선택 텍스트는 None이다."""
    # when: None이나 공백만 든 텍스트를 선택 검증한다
    result = optional_text(None, "이름", max_length=50)
    # then: None으로 정규화된다
    assert result is None
    assert optional_text("   ", "이름", max_length=50) is None
