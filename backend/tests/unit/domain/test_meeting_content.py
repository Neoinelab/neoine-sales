"""MeetingContent(AC17, P7): 앞뒤 공백(줄바꿈 포함) 제거 후 비면 거절, NUL 거절, 길이 제한 없음."""

import pytest
from app.domain.partner_meeting.values import MeetingContent

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

CONTENT_REQUIRED = "미팅 내용을 입력하세요."


@pytest.mark.parametrize("raw", ["", "   ", "  \n ", "\n\n", "\t \r\n"])
def test_blank_after_strip_is_rejected_with_the_required_message(raw: str) -> None:
    with raises_with(InvalidValueError, CONTENT_REQUIRED):
        MeetingContent(raw)


def test_inner_newlines_are_kept_and_edges_are_stripped() -> None:
    assert MeetingContent("\n a\nb \n").value == "a\nb"


def test_inner_spaces_are_kept() -> None:
    assert MeetingContent("  견적 논의  완료 ").value == "견적 논의  완료"


@pytest.mark.parametrize("raw", ["a\x00b", "\x00", " abc\x00 "])
def test_nul_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        MeetingContent(raw)


def test_there_is_no_length_limit() -> None:
    long_text = "가" * 100_000

    assert MeetingContent(long_text).value == long_text


def test_equal_contents_compare_equal_after_normalization() -> None:
    assert MeetingContent(" a ") == MeetingContent("a")
