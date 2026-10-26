"""R4 AC4-1·4-4: 다음 Action을 기록하며 이전 Next Action을 종료(수행)로 닫는 도메인 규칙."""

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


def test_open_next_action_closes_as_done_without_memo_change() -> None:
    action = make_deal_action(memo="기존 메모")

    change = action.close_as_done_for_next_update(later(60))

    assert change == NextActionStatusChange(
        before=NextActionStatus.OPEN, after=NextActionStatus.DONE, note=""
    )
    assert action.next_action_state == NextActionState.of(NextActionStatus.DONE, later(60))
    assert action.content.memo == "기존 메모"
    assert action.updated_at == later(60)


def test_open_next_action_without_memo_keeps_memo_empty() -> None:
    action = make_deal_action(memo="")

    action.close_as_done_for_next_update(later(60))

    assert action.content.memo == ""


@pytest.mark.parametrize("closed", [NextActionStatus.DONE, NextActionStatus.NOT_DONE])
def test_closed_next_action_is_left_unchanged(closed: NextActionStatus) -> None:
    action = make_deal_action()
    action.change_next_action_status(closed, "", later(10))
    state = action.next_action_state
    content = action.content

    change = action.close_as_done_for_next_update(later(60))

    assert change is None
    assert action.next_action_state == state
    assert action.content == content
    assert action.updated_at == later(10)


def test_action_without_next_action_cannot_be_closed() -> None:
    action = make_deal_action(next_action="")

    with raises_with(InvalidStateError, NO_NEXT_ACTION):
        action.close_as_done_for_next_update(later(60))

    assert action.next_action_state is None
    assert action.updated_at == NOW
