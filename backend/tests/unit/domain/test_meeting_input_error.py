"""MeetingInputError: 위반을 위치와 함께 모은다. 문구는 첫 위반이다."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.partner_meeting import errors
from app.domain.partner_meeting.errors import (
    COMPANY_NOT_FOUND,
    NO_ITEMS,
    MeetingInputError,
    MeetingIssue,
    PartnerMeetingNotFoundError,
)
from tests.support.expect import raises_with


def test_the_message_is_the_first_issue_message() -> None:
    """오류 문구는 첫 위반의 문구다."""
    # given: 위반 둘
    first = MeetingIssue(("items", 0, "partner_company"), COMPANY_NOT_FOUND)
    second = MeetingIssue(("items", 1, "meeting_date"), "미팅 날짜를 입력하세요.")
    # when: 두 위반으로 오류를 만든다
    error = MeetingInputError((first, second))
    # then: 문구는 첫 위반이고 위반 목록은 그대로다
    assert str(error) == COMPANY_NOT_FOUND
    assert error.issues == (first, second)


def test_an_empty_issue_list_is_rejected() -> None:
    """위반이 없는 오류는 만들 수 없다."""
    # when·then: 빈 위반 목록이면 ValueError다
    with pytest.raises(ValueError, match=r"."):
        MeetingInputError(())


def test_the_error_is_an_invalid_value_error() -> None:
    """위반 오류는 InvalidValueError의 하위 타입이다."""
    # when: 위반 하나로 오류를 만든다
    error = MeetingInputError((MeetingIssue(("content",), "미팅 내용을 입력하세요."),))
    # then: InvalidValueError다
    assert isinstance(error, InvalidValueError)


def test_issue_locations_can_mix_names_and_indexes() -> None:
    """위반 위치는 이름과 번호가 섞일 수 있다."""
    # when: 이름과 번호가 섞인 위치로 위반을 만든다
    issue = MeetingIssue(("items", 3, "content"), "x")
    # then: 위치가 그대로다
    assert issue.location == ("items", 3, "content")


def test_the_user_facing_constants_are_fixed() -> None:
    """사용자에게 보이는 문구 상수는 고정이다."""
    # when·then: 상수 문구를 읽으면 명세와 같다
    assert COMPANY_NOT_FOUND == "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."
    assert NO_ITEMS == "입력한 미팅이 없습니다."


def test_the_deal_messages_are_gone() -> None:
    """Deal 관련 문구 상수는 없다."""
    # when·then: 모듈을 살피면 DEAL_NOT_FOUND·DEAL_NOT_LINKED가 없다
    assert not hasattr(errors, "DEAL_NOT_FOUND")
    assert not hasattr(errors, "DEAL_NOT_LINKED")


def test_not_found_has_the_documented_message() -> None:
    """없는 기록 오류의 문구는 명세와 같다."""
    # when·then: 오류를 던지면 "미팅 기록을 찾을 수 없습니다." 문구다
    with raises_with(PartnerMeetingNotFoundError, "미팅 기록을 찾을 수 없습니다."):
        raise PartnerMeetingNotFoundError(1)
