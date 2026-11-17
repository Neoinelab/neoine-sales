"""다음 Action을 기록하며 이전 Next Action을 종료(수행)로 닫는 도메인 규칙."""

import pytest

from app.domain.common.errors import InvalidStateError
from app.domain.deal_action.next_action_status import (
    NextActionState,
    NextActionStatus,
    NextActionStatusChange,
)
from tests.factories import NOW, later, make_deal_action
from tests.support.expect import raises_with

NO_NEXT_ACTION = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."


def test_open_next_action_closes_as_done_without_changing_the_content() -> None:
    """열린 Next Action은 내용을 바꾸지 않고 종료(수행)가 된다(Comment도 만들지 않는다).

    테스트 코드: AC-036
    """
    # given: Open Next Action
    action = make_deal_action()
    content = action.content

    # when: 다음 기록을 위해 종료(수행)로 닫는다
    change = action.close_as_done_for_next_update(later(60))

    # then: Open에서 done으로 바뀌었다고 알리고 note는 비어 있다(Comment 없음)
    assert change == NextActionStatusChange(
        before=NextActionStatus.OPEN, after=NextActionStatus.DONE, note=""
    )
    # then: 상태·종료 시각·수정 시각이 새로 정해지고 내용은 그대로다
    assert action.next_action_state == NextActionState.of(NextActionStatus.DONE, later(60))
    assert action.content == content
    assert action.updated_at == later(60)


@pytest.mark.parametrize("closed", [NextActionStatus.DONE, NextActionStatus.NOT_DONE])
def test_closed_next_action_is_left_unchanged(closed: NextActionStatus) -> None:
    """이미 종료된 Next Action은 그대로 둔다.

    테스트 코드: AC-040
    """
    # given: 종료(수행)나 미수행으로 닫은 Action
    action = make_deal_action()
    action.change_next_action_status(closed, "", later(10))
    state = action.next_action_state
    content = action.content

    # when: 다음 기록을 위해 닫으려 한다
    change = action.close_as_done_for_next_update(later(60))

    # then: 변경 없음이고 상태·내용·수정 시각이 그대로다
    assert change is None
    assert action.next_action_state == state
    assert action.content == content
    assert action.updated_at == later(10)


def test_action_without_next_action_cannot_be_closed() -> None:
    """Next Action이 없는 Action은 닫을 수 없다."""
    # given: 진행사항만 있는 Action
    action = make_deal_action(next_action="")

    # when·then: 닫으려 하면 상태 오류다
    with raises_with(InvalidStateError, NO_NEXT_ACTION):
        action.close_as_done_for_next_update(later(60))

    # then: 상태와 수정 시각이 그대로다
    assert action.next_action_state is None
    assert action.updated_at == NOW
