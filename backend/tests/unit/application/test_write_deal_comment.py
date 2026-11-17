"""WriteDealComment: Deal(또는 그 Deal의 Action)에 Comment를 쓴다.

판정 순서는 없는 Deal(404) -> 본문(422) -> 연결 Action(422)이고, 성공하면 Comment와 이력이 한
트랜잭션이다. 쓰기 권한(user 403)은 웹 규칙이라 여기서 보지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.value_objects import DealActionId
from app.domain.deal_comment.entities import DealComment
from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.action_env import BOSS, KIM, PARK
from tests.unit.application.comment_env import (
    ACTION_NOT_IN_DEAL,
    BLANK,
    DEAL_NOT_FOUND,
    NUL,
)

if TYPE_CHECKING:
    from tests.unit.application.comment_env import CommentEnv


async def test_a_sales_who_is_not_the_owner_writes_a_deal_comment_with_server_decided_values(
    comment_env: CommentEnv,
) -> None:
    """sales가 Deal Comment를 쓰면 작성자·시각을 서버가 정하고 Action 연결은 없다.

    테스트 코드: CM-001
    """
    # given: Deal(Owner는 PARK이 아니다)과 커밋 횟수
    commits = comment_env.uow.commits

    # when: PARK이 본문 "고객사 예산 회의 예정"으로 쓴다
    written = await comment_env.say(PARK, "고객사 예산 회의 예정")

    # then: 소속 Deal·작성자·시각이 서버 값이고 연결 Action은 없다
    assert isinstance(written, DealComment)
    assert written.deal_code.value == comment_env.code
    assert written.action_id is None
    assert written.author_user_id == PARK.user_id
    assert written.created_at == written.updated_at == comment_env.clock.now()
    # then: 저장되었고 커밋은 1번이다
    assert [c.id for c in await comment_env.stored()] == [written.id]
    assert comment_env.uow.commits == commits + 1


async def test_the_body_is_trimmed_at_both_ends_and_a_long_body_is_kept_whole(
    comment_env: CommentEnv,
) -> None:
    """본문은 앞뒤 공백만 지우고 안쪽 줄바꿈·20,000자를 그대로 저장한다.

    테스트 코드: CM-002
    """
    # when: 앞뒤 공백과 안쪽 줄바꿈이 있는 본문, 이어서 20,000자 본문으로 쓴다
    first = await comment_env.say(KIM, "  첫 줄\n  둘째 줄  ")
    second = await comment_env.say(KIM, "가" * 20_000)

    # then: 저장된 첫 본문은 앞뒤만 지워지고 둘째는 20,000자 그대로다
    stored = {c.id: c.body for c in await comment_env.stored()}
    assert stored[first.id] == "첫 줄\n  둘째 줄"
    assert stored[second.id] == "가" * 20_000


@pytest.mark.parametrize("body", ["", "  \n "], ids=["empty", "blank"])
async def test_a_blank_body_is_rejected_and_nothing_is_saved(
    comment_env: CommentEnv, body: str
) -> None:
    """본문이 비었거나 공백뿐이면 422이고 Comment·이력·커밋이 그대로다.

    테스트 코드: CM-003
    """
    # given: 쓰기 전 커밋 횟수와 이력
    commits = comment_env.uow.commits
    rows = await comment_env.rows()

    # when·then: 빈 본문은 "Comment를 입력하세요."로 거절된다
    with raises_with(InvalidValueError, BLANK):
        await comment_env.say(KIM, body)

    # then: Comment·이력·커밋이 늘지 않는다
    assert await comment_env.stored() == []
    assert await comment_env.rows() == rows
    assert comment_env.uow.commits == commits


@pytest.mark.parametrize("body", ["가\x00나", "\x00"], ids=["inside", "only-nul"])
async def test_nul_in_the_body_is_rejected_before_the_blank_check(
    comment_env: CommentEnv, body: str
) -> None:
    """본문에 NUL이 있으면 422이고 NUL 판정이 빈 값 판정보다 먼저다(아무것도 저장되지 않는다).

    테스트 코드: CM-004
    """
    # when·then: NUL 문구로 거절된다
    with raises_with(InvalidValueError, NUL):
        await comment_env.say(KIM, body)

    # then: 아무것도 저장되지 않았다
    assert await comment_env.stored() == []


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_a_missing_or_malformed_deal_code_is_not_found_even_with_a_bad_body(
    comment_env: CommentEnv, code: str
) -> None:
    """없는 Deal·형식이 틀린 code는 본문이 잘못돼도 404가 먼저다.

    테스트 코드: CM-006
    """
    # when·then: 빈 본문으로 써도 Deal 없음 오류다
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await comment_env.say(KIM, "", code=code)


async def test_linking_an_action_of_the_deal_makes_an_action_comment_even_for_others_actions(
    comment_env: CommentEnv,
) -> None:
    """그 Deal의 Action을 연결하면 같은 Deal 소속 Action Comment가 되고 남의 Action에도 쓸 수 있다.

    테스트 코드: CM-008
    """
    # given: KIM이 작성한 Action A (comment_env.action)
    action = comment_env.action

    # when: PARK이 A에 연결한 Comment를 쓴다
    written = await comment_env.say(PARK, "견적서 초안 공유함", action_id=action.id)

    # then: 소속 Deal은 D, 연결 Action은 A, 작성자는 PARK이다
    assert written.deal_code.value == comment_env.code
    assert written.action_id == action.id
    assert written.author_user_id == PARK.user_id
    # then: 그 Deal 목록과 Action 필터 목록 양쪽에서 읽힌다
    listed = await comment_env.list.execute(comment_env.code, None)
    filtered = await comment_env.list.execute(comment_env.code, action.id)
    assert written.id in [c.comment.id for c in listed]
    assert [c.comment.id for c in filtered] == [written.id]


@pytest.mark.parametrize("which", ["other-deal", "missing"])
async def test_linking_an_action_of_another_deal_or_a_missing_one_is_rejected(
    comment_env: CommentEnv, which: str
) -> None:
    """다른 Deal의 Action·없는 Action을 연결하면 422이고 아무것도 저장되지 않는다.

    테스트 코드: CM-009
    """
    # given: 다른 Deal E와 그 Action B
    other_code, foreign = await comment_env.other_deal()
    action_id = foreign.id if which == "other-deal" else DealActionId(MISSING_ID)
    rows = await comment_env.rows()
    commits = comment_env.uow.commits

    # when·then: D에 그 Action을 연결해 쓰면 "선택한 Action이 이 Deal에 없습니다."로 거절된다
    with raises_with(InvalidValueError, ACTION_NOT_IN_DEAL):
        await comment_env.say(KIM, "본문", action_id=action_id)

    # then: D·E의 Comment와 D의 이력, 커밋이 그대로다
    assert await comment_env.stored() == []
    assert await comment_env.stored(other_code) == []
    assert await comment_env.rows() == rows
    assert comment_env.uow.commits == commits


async def test_the_body_error_is_reported_before_the_linked_action_error(
    comment_env: CommentEnv,
) -> None:
    """본문 오류와 연결 Action 오류가 함께 있으면 본문 422가 먼저다.

    테스트 코드: CM-009
    """
    # given: 다른 Deal의 Action B
    _, foreign = await comment_env.other_deal()

    # when·then: 빈 본문과 B를 함께 쓰면 본문 오류다
    with raises_with(InvalidValueError, BLANK):
        await comment_env.say(KIM, "", action_id=foreign.id)


async def test_the_history_records_a_deal_comment_and_an_action_comment_with_their_targets(
    comment_env: CommentEnv,
) -> None:
    """작성 이력은 구분 comment이고 대상이 Deal Comment는 "Comment", Action Comment는 수행일·유형을
    붙인다.

    테스트 코드: CM-010
    """
    # given: 수행일과 유형이 정해진 Action A
    action = comment_env.action
    target = f"Action Comment ({action.acted_on.isoformat()} 미팅)"

    # when: KIM이 Deal Comment, 이어서 A의 Action Comment를 쓴다
    await comment_env.say(KIM, "예산 확인")
    await comment_env.say(KIM, "자료 전달", action_id=action.id)

    # then: comment 구분 이력이 두 줄이고 변경 전은 비며 변경 후는 "등록: 본문"이다
    assert await comment_env.comment_rows() == [
        ("comment", "Comment", "", "등록: 예산 확인"),
        ("comment", target, "", "등록: 자료 전달"),
    ]
    # then: 변경자는 KIM이고 시각은 요청 시각이다
    entry = (await comment_env.actions.entries())[-1]
    assert entry.changed_by == KIM.user_id
    assert entry.changed_at == comment_env.clock.now()


async def test_a_long_body_is_clipped_in_the_history_only(comment_env: CommentEnv) -> None:
    """긴 본문은 이력에서만 잘리고 Comment 원문은 그대로다.

    테스트 코드: CM-011
    """
    # when: 1,500자 본문으로 쓴다
    written = await comment_env.say(KIM, "가" * 1_500)

    # then: Comment 본문은 1,500자 그대로다
    assert [c.body for c in await comment_env.stored()] == ["가" * 1_500]
    assert written.body == "가" * 1_500
    # then: 이력 변경 후는 "등록: " + 본문 앞부분으로 999자 + "…"다
    (row,) = await comment_env.comment_rows()
    assert len(row[3]) == 1_000
    assert row[3] == ("등록: " + "가" * 1_500)[:999] + "…"


async def test_writing_leaves_the_deal_and_the_action_untouched(comment_env: CommentEnv) -> None:
    """Comment 작성은 Deal 값·수정 시각·최종 업데이트와 Action 수정 시각·내용을 바꾸지 않는다.

    테스트 코드: CM-012
    """
    # given: 쓰기 전 Deal 상세 값과 Action 값
    env = comment_env.actions.env
    deal_before = (await env.get.execute(comment_env.code)).item
    deal_row_before = await env.uow.deals.get(deal_before.deal.id)
    action_before = await comment_env.actions.stored(comment_env.action.id)

    # when: Deal Comment와 A의 Action Comment를 쓴다
    await comment_env.say(KIM, "딜 글")
    await comment_env.say(KIM, "액션 글", action_id=comment_env.action.id)

    # then: Deal 상세 값(Next Action·최종 업데이트 포함)과 수정 시각이 그대로다
    assert (await env.get.execute(comment_env.code)).item == deal_before
    assert (await env.uow.deals.get(deal_before.deal.id)).updated_at == deal_row_before.updated_at
    # then: Action의 내용과 수정 시각이 그대로다
    action_after = await comment_env.actions.stored(comment_env.action.id)
    assert action_after.content == action_before.content
    assert action_after.updated_at == action_before.updated_at


async def test_an_admin_may_comment_on_any_action(comment_env: CommentEnv) -> None:
    """admin도 남의 Action에 Comment를 쓴다(Action 작성자 여부는 보지 않는다).

    테스트 코드: CM-008
    """
    # when: admin이 KIM의 Action에 쓴다
    written = await comment_env.say(BOSS, "관리자 메모", action_id=comment_env.action.id)

    # then: 작성자는 admin이다
    assert written.author_user_id == BOSS.user_id
