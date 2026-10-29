"""MeetingInputError(AC17): 위반을 위치와 함께 모은다. 문구는 첫 위반이다."""

import pytest
from app.domain.partner_meeting.errors import (
    COMPANY_NOT_FOUND,
    DEAL_NOT_FOUND,
    DEAL_NOT_LINKED,
    NO_ITEMS,
    MeetingInputError,
    MeetingIssue,
    PartnerMeetingNotFoundError,
)

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with


def test_the_message_is_the_first_issue_message() -> None:
    first = MeetingIssue(("items", 0, "partner_company"), COMPANY_NOT_FOUND)
    second = MeetingIssue(("items", 1, "deal_code"), DEAL_NOT_LINKED)

    error = MeetingInputError((first, second))

    assert str(error) == COMPANY_NOT_FOUND
    assert error.issues == (first, second)


def test_an_empty_issue_list_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"."):
        MeetingInputError(())


def test_the_error_is_an_invalid_value_error() -> None:
    error = MeetingInputError((MeetingIssue(("content",), "미팅 내용을 입력하세요."),))

    assert isinstance(error, InvalidValueError)


def test_issue_locations_can_mix_names_and_indexes() -> None:
    issue = MeetingIssue(("items", 3, "content"), "x")

    assert issue.location == ("items", 3, "content")


def test_the_user_facing_constants_are_fixed() -> None:
    assert COMPANY_NOT_FOUND == "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."
    assert DEAL_NOT_FOUND == "Deal을 찾을 수 없습니다. 목록에서 다시 선택하세요."
    assert DEAL_NOT_LINKED == "선택한 파트너와 연결된 Deal이 아닙니다."
    assert NO_ITEMS == "입력한 미팅이 없습니다."


def test_not_found_has_the_documented_message() -> None:
    with raises_with(PartnerMeetingNotFoundError, "미팅 기록을 찾을 수 없습니다."):
        raise PartnerMeetingNotFoundError(1)
