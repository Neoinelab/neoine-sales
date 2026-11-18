"""GetDeal·RegisterDeal·UpdateDeal: 응답 view의 `item.unread_comment_count`(CM-R47)."""

from typing import TYPE_CHECKING

from tests.factories_deal import SALES, make_patch
from tests.unit.application.action_env import PARK

if TYPE_CHECKING:
    from tests.unit.application.comment_env import CommentEnv


async def test_detail_update_and_registration_views_carry_the_unread_count(
    comment_env: CommentEnv,
) -> None:
    """상세·수정·등록 응답 view에도 읽지 않은 수가 있다(등록은 0).

    테스트 코드: CM-087
    """
    # given: D에 읽지 않은 Comment 2건
    env = comment_env.actions.env
    await comment_env.say(PARK, "one")
    await comment_env.say(PARK, "two", action_id=comment_env.action.id)

    # when: 상세를 읽고, Deal Name을 고치고, 새 Deal을 등록한다
    detail = await env.get.execute(comment_env.code)
    updated = await env.update.execute(comment_env.code, make_patch(name="이름 변경"), SALES)
    registered = await env.new_deal()

    # then: 상세 2, 수정 응답 2, 새 Deal 0이다
    assert detail.item.unread_comment_count == 2
    assert updated.item.unread_comment_count == 2
    assert registered.item.unread_comment_count == 0
