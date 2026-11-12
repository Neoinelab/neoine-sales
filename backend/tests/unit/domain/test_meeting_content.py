"""MeetingContent: 앞뒤 공백(줄바꿈 포함) 제거 후 비면 거절, NUL 거절, 길이 제한 없음."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.partner_meeting.values import MeetingContent
from tests.support.expect import raises_with

CONTENT_REQUIRED = "미팅 내용을 입력하세요."


@pytest.mark.parametrize("raw", ["", "   ", "  \n ", "\n\n", "\t \r\n"])
def test_blank_after_strip_is_rejected_with_the_required_message(raw: str) -> None:
    """공백뿐인 내용은 필수 문구로 거절된다."""
    # when·then: 공백뿐인 내용을 만들면 "미팅 내용을 입력하세요." 오류다
    with raises_with(InvalidValueError, CONTENT_REQUIRED):
        MeetingContent(raw)


def test_inner_newlines_are_kept_and_edges_are_stripped() -> None:
    """앞뒤는 정리하고 가운데 줄바꿈은 남긴다."""
    # when: 앞뒤에 줄바꿈·공백이 붙은 내용을 만든다
    content = MeetingContent("\n a\nb \n")
    # then: 가운데 줄바꿈만 남는다
    assert content.value == "a\nb"


def test_inner_spaces_are_kept() -> None:
    """가운데 공백은 그대로 둔다."""
    # when: 가운데에 공백이 둘 있는 내용을 만든다
    content = MeetingContent("  견적 논의  완료 ")
    # then: 가운데 공백이 남는다
    assert content.value == "견적 논의  완료"


@pytest.mark.parametrize("raw", ["a\x00b", "\x00", " abc\x00 "])
def test_nul_is_rejected(raw: str) -> None:
    """NUL이 든 내용은 거절된다."""
    # when·then: NUL이 있으면 거절된다
    with pytest.raises(InvalidValueError, match="NUL"):
        MeetingContent(raw)


def test_there_is_no_length_limit() -> None:
    """내용 길이에 제한이 없다."""
    # given: 10만 자 내용
    long_text = "가" * 100_000
    # when: 내용을 만든다
    content = MeetingContent(long_text)
    # then: 그대로 보존된다
    assert content.value == long_text


def test_equal_contents_compare_equal_after_normalization() -> None:
    """정리한 뒤 같은 내용은 같은 값이다."""
    # when·then: 앞뒤 공백만 다른 두 내용은 같다
    assert MeetingContent(" a ") == MeetingContent("a")
