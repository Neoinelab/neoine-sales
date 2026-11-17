"""Comment 생성 때의 읽음 상태(CM-R26): 작성자가 그 순간의 Deal Owner이면 읽음, 아니면 읽지 않음.

작성 API·Action 등록 `comment`·종료 Comment 세 경로가 같은 규칙을 따른다. 공통 Given의 Deal D는
Owner가 KIM이다.
"""

from typing import TYPE_CHECKING

from tests.unit.application.action_env import BOSS, KIM, PARK

if TYPE_CHECKING:
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.deal_comment.entities import DealComment
    from tests.unit.application.comment_env import CommentEnv


async def _of_action(comment_env: CommentEnv, action_id: DealActionId) -> list[DealComment]:
    return [c for c in await comment_env.stored() if c.action_id == action_id]


async def test_the_owners_comment_is_born_read_and_others_including_admin_are_unread(
    comment_env: CommentEnv,
) -> None:
    """Owner가 쓴 Comment는 읽음(작성 시각)으로, 다른 sales·admin이 쓴 것은 읽지 않음으로 생긴다.

    테스트 코드: CM-048
    """
    # given: D의 Owner는 KIM, Action A(작성자 KIM)

    # when: KIM이 D에, PARK이 A에, admin이 D에 Comment를 쓴다
    k1 = await comment_env.say(KIM, "k1")
    p1 = await comment_env.say(PARK, "p1", action_id=comment_env.action.id)
    r1 = await comment_env.say(BOSS, "r1")

    # then: k1은 작성 시각이 읽음 시각이고 p1·r1은 읽지 않음이다
    assert await comment_env.read_at(k1.id) == k1.created_at
    assert await comment_env.read_at(p1.id) is None
    assert await comment_env.read_at(r1.id) is None


async def test_a_comment_left_with_an_action_registration_is_read_only_for_the_owner(
    comment_env: CommentEnv,
) -> None:
    """Action 등록 comment는 등록자가 Owner일 때만 읽음이다.

    테스트 코드: CM-048
    """
    # when: PARK이, 이어서 KIM(Owner)이 comment와 함께 Action을 등록한다
    by_park = await comment_env.actions.act(PARK, comment="현장 사진 공유")
    by_owner = await comment_env.actions.act(KIM, comment="내가 남김")

    # then: PARK의 Comment는 읽지 않음, KIM의 Comment는 작성 시각이 읽음 시각이다
    (park_comment,) = await _of_action(comment_env, by_park.id)
    (owner_comment,) = await _of_action(comment_env, by_owner.id)
    assert park_comment.read_at is None
    assert owner_comment.read_at == owner_comment.created_at


async def test_a_closing_comment_is_read_only_when_the_owner_closes(
    comment_env: CommentEnv,
) -> None:
    """종료 Comment는 닫는 사람이 Owner일 때만 읽음이고 admin이 닫으면 읽지 않음이다.

    테스트 코드: CM-048
    """
    # given: Next Action이 있는 Action 둘(둘 다 KIM의 Action)
    first = await comment_env.actions.act(KIM)
    second = await comment_env.actions.act(KIM)

    # when: admin이 첫째를, Owner KIM이 둘째를 종료 Comment와 함께 닫는다
    await comment_env.actions.set_status(first.id, BOSS, "done", "확인 부탁")
    await comment_env.actions.set_status(second.id, KIM, "done", "완료했습니다")

    # then: admin의 종료 Comment는 읽지 않음, Owner의 것은 읽음이다
    (by_admin,) = await _of_action(comment_env, first.id)
    (by_owner,) = await _of_action(comment_env, second.id)
    assert by_admin.read_at is None
    assert by_owner.read_at == by_owner.created_at
