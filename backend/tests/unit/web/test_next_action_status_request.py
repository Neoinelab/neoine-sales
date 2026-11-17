"""NextActionStatusRequest: 상태 변경 본문의 형식 검증."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.deal_action.next_action_status import NextActionStatus
from app.web.schemas.deal_action import NextActionStatusRequest


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "closed"},
        {"status": "notDone"},
        {"status": "DONE"},
        {"status": None},
        {"status": "done", "comment": 1},
        {"status": "done", "memo": "전달 완료"},
        {"status": "done", "closed_at": "2027-01-01T00:00:00Z"},
    ],
)
def test_malformed_status_bodies_are_rejected(body: dict[str, Any]) -> None:
    """상태 값·형식이 틀리거나 모르는 필드가 있는 본문은 요청 형식 오류다.

    테스트 코드: NA-016, CM-036
    """
    # when·then: 누락·세 값 밖·null·숫자 comment·예전 memo 키·모르는 필드는 ValidationError다
    with pytest.raises(ValidationError):
        NextActionStatusRequest.model_validate(body)


def test_comment_defaults_to_an_empty_string() -> None:
    """comment를 생략하면 빈 문자열로 받아들인다.

    테스트 코드: NA-016, CM-033
    """
    # when: status만 있는 본문을 검증한다
    request = NextActionStatusRequest.model_validate({"status": "done"})
    # then: comment는 빈 문자열이고 입력으로 바뀐다
    assert request.comment == ""
    data = request.to_input()
    assert (data.status, data.comment) == (NextActionStatus.DONE, "")


def test_comment_is_passed_to_the_input_untouched() -> None:
    """comment는 입력으로 그대로 넘어간다(trim·검증은 유스케이스가 한다).

    테스트 코드: CM-031
    """
    # when: comment가 있는 본문을 검증하고 입력으로 바꾼다
    request = NextActionStatusRequest.model_validate({"status": "done", "comment": "  전달 완료 "})
    # then: 입력의 comment가 그대로다
    assert request.to_input().comment == "  전달 완료 "
