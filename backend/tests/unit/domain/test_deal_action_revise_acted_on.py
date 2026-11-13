"""DealAction.revise의 수행일 인자: 수행일만·내용만·둘 다·둘 다 같음의 반환값과 부수 효과."""

import pytest

from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from tests.factories import date_after, later, make_action_content, make_deal_action

NEW_DAY = date_after(-3)


def test_revise_with_only_a_new_acted_on_changes_it_and_touches_updated_at() -> None:
    """내용이 같아도 새 수행일을 주면 수행일이 바뀌고 수정 시각이 갱신된다.

    테스트 코드: AC-118
    """
    # given: 기본 Action
    action = make_deal_action()
    content = action.content

    # when: 같은 내용에 새 수행일로 고친다
    changed = action.revise(make_action_content(), later(30), acted_on=NEW_DAY)

    # then: 바뀌었다고 알리고 수행일·수정 시각이 새 값이며 내용은 그대로다
    assert changed is True
    assert (action.acted_on, action.updated_at) == (NEW_DAY, later(30))
    assert action.content == content


def test_revise_with_a_new_acted_on_and_new_content_changes_both() -> None:
    """수행일과 내용을 함께 주면 둘 다 바뀐다.

    테스트 코드: AC-119
    """
    # given: 기본 Action
    action = make_deal_action()

    # when: 새 내용과 새 수행일로 고친다
    changed = action.revise(make_action_content(action="제안 발표"), later(30), acted_on=NEW_DAY)

    # then: 둘 다 반영된다
    assert changed is True
    assert (action.content.action, action.acted_on) == ("제안 발표", NEW_DAY)


@pytest.mark.parametrize("same", [False, True], ids=["omitted", "same-date"])
def test_revise_with_same_content_and_same_or_no_acted_on_is_not_a_change(same: bool) -> None:
    """내용도 수행일도 같으면(생략·같은 날짜) 바뀌지 않았다고 알리고 아무것도 바꾸지 않는다.

    테스트 코드: AC-120
    """
    # given: 기본 Action
    action = make_deal_action()
    before_day = action.acted_on

    # when: 같은 내용에 수행일을 생략하거나 같은 날짜로 고친다
    changed = action.revise(make_action_content(), later(30), acted_on=before_day if same else None)

    # then: 변경 없음이고 수행일·수정 시각이 그대로다
    assert changed is False
    assert (action.acted_on, action.updated_at) == (before_day, make_deal_action().updated_at)


def test_revise_with_no_acted_on_keeps_it_when_only_the_content_changes() -> None:
    """수행일을 주지 않고 내용만 고치면 수행일이 그대로다.

    테스트 코드: AC-120, AC-103
    """
    # given: 기본 Action
    action = make_deal_action()
    before_day = action.acted_on

    # when: 수행일 없이 내용만 고친다
    changed = action.revise(make_action_content(action="다른 내용"), later(30))

    # then: 내용만 바뀐다
    assert changed is True
    assert action.acted_on == before_day


def test_revise_acted_on_keeps_the_closed_next_action_state_and_actor() -> None:
    """수행일을 고쳐도 Next Action 상태·종료일·담당자·스냅숏·등록 시각은 그대로다.

    테스트 코드: AC-118, AC-126
    """
    # given: 종료(수행)한 Next Action이 있는 Action
    action = make_deal_action()
    action.change_next_action_status(NextActionStatus.DONE, "", later(10))
    state: NextActionState | None = action.next_action_state
    actor, snapshot, created_at = action.actor_user_id, action.snapshot, action.created_at

    # when: 종료일보다 앞선 수행일로 고친다
    action.revise(make_action_content(), later(30), acted_on=NEW_DAY)

    # then: 상태·종료일·담당자·스냅숏·등록 시각이 그대로다
    assert action.next_action_state == state
    assert (action.actor_user_id, action.snapshot, action.created_at) == (
        actor,
        snapshot,
        created_at,
    )
