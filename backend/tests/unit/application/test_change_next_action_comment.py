"""ChangeNextActionStatus의 종료 Comment: 작성자 규칙과 검사 순서.

종료 Comment는 그 Action의 Action Comment가 된다(작성자 = 요청자). 검사 순서는
Comment NUL -> Open+Comment -> Next Action 없음 -> 같은 상태이고, 거절되면 Comment가 생기지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal_action.next_action_status import NextActionStatus
from tests.support.expect import raises_with
from tests.unit.application.action_env import BOSS, KIM

if TYPE_CHECKING:
    from app.domain.deal_action.value_objects import DealActionId
    from tests.unit.application.action_env import ActionEnv

OPEN_WITH_COMMENT = "Open으로 되돌릴 때는 Comment를 남길 수 없습니다."
NUL = "Comment에는 NUL 문자를 쓸 수 없습니다"
NO_NEXT_ACTION = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."


async def _comments(action_env: ActionEnv) -> list[tuple[DealActionId | None, str, object]]:
    found = await action_env.env.uow.deal_comments.list_for_deal(action_env.deal.item.deal.id)
    return [(c.action_id, c.body, c.author_user_id) for c in found]


async def test_an_admin_closing_someone_elses_action_becomes_the_comment_author(
    action_env: ActionEnv,
) -> None:
    """admin이 남의 Action을 종료 Comment와 함께 닫으면 Comment 작성자와 이력 변경자는 admin이다.

    테스트 코드: CM-032
    """
    # given: KIM의 Open Action
    action = await action_env.act(KIM)

    # when: admin이 not_done, Comment "고객 일정 취소"로 바꾼다
    await action_env.set_status(action.id, BOSS, "not_done", "고객 일정 취소")

    # then: 상태는 not_done이고 생긴 Comment의 작성자는 admin이다
    stored = await action_env.stored(action.id)
    assert stored.next_action_state is not None
    assert stored.next_action_state.status is NextActionStatus.NOT_DONE
    assert await _comments(action_env) == [(action.id, "고객 일정 취소", BOSS.user_id)]
    # then: 이력 두 줄(Next Action, Comment 등록)의 변경자도 admin이다
    assert {e.changed_by for e in (await action_env.entries())[-2:]} == {BOSS.user_id}


async def test_the_original_author_cannot_delete_a_comment_an_admin_left_when_closing(
    action_env: ActionEnv,
) -> None:
    """admin이 종료하며 남긴 Comment는 Action 작성자 KIM이 지울 수 없다(403).

    테스트 코드: CM-032
    """
    # given: admin이 KIM의 Action을 Comment와 함께 닫았다
    from app.application.deal_comment.delete_deal_comment import (  # noqa: PLC0415
        DeleteDealComment,
    )
    from app.domain.deal_comment.errors import DealCommentDeleteForbiddenError  # noqa: PLC0415

    action = await action_env.act(KIM)
    await action_env.set_status(action.id, BOSS, "done", "관리자 종료")
    (comment,) = await action_env.env.uow.deal_comments.list_for_deal(action.deal_code)

    # when·then: KIM이 그 Comment를 지우면 403이다(Action 작성자라는 이유로 지울 수 없다)
    delete = DeleteDealComment(action_env.env.uow_factory, action_env.env.clock)
    with pytest.raises(DealCommentDeleteForbiddenError):
        await delete.execute(comment.id, KIM)


async def test_the_checks_run_in_the_documented_order_and_a_rejection_makes_no_comment(
    action_env: ActionEnv,
) -> None:
    """검사는 NUL -> Open+Comment -> Next Action 없음 -> 같은 상태 순서이고 거절되면 Comment가 없다.

    테스트 코드: CM-035
    """
    # given: 진행사항만 Action P, Open Action A, 종료(수행) Action Q
    progress_only = await action_env.act(KIM, next_action="")
    open_action = await action_env.act(KIM)
    closed = await action_env.act(KIM)
    await action_env.set_status(closed.id, KIM, "done")
    rows = await action_env.rows()

    # when·then: P에 open+Comment는 Open+Comment 422(Next Action 없음 409가 아니다)
    with raises_with(InvalidValueError, OPEN_WITH_COMMENT):
        await action_env.set_status(progress_only.id, KIM, "open", "메모")
    # when·then: Open인 A에 open+NUL은 NUL 422(같은 상태 409가 아니다)
    with raises_with(InvalidValueError, NUL):
        await action_env.set_status(open_action.id, KIM, "open", "가\x00나")
    # when·then: P에 done+NUL은 NUL 422(Next Action 없음 409가 아니다)
    with raises_with(InvalidValueError, NUL):
        await action_env.set_status(progress_only.id, KIM, "done", "가\x00나")
    # when·then: Q에 done+Comment는 같은 상태 409다
    with raises_with(InvalidStateError, "이미 종료(수행) 상태입니다."):
        await action_env.set_status(closed.id, KIM, "done", "또 종료")
    # when·then: P에 done+Comment는 Next Action 없음 409다
    with raises_with(InvalidStateError, NO_NEXT_ACTION):
        await action_env.set_status(progress_only.id, KIM, "done", "메모")

    # then: 어느 경우에도 Comment가 생기지 않고 이력이 그대로다
    assert await _comments(action_env) == []
    assert await action_env.rows() == rows
