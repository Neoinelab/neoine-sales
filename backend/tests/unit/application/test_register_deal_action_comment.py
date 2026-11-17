"""RegisterDealAction의 `comment`: 새 Action의 Action Comment를 같은 트랜잭션에서 함께 남긴다.

판정 위치는 내용 422 바로 다음·수행일 422 앞이고, 등록이 거절되면 Comment도 남지 않는다.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal_action.value_objects import DealActionId
from tests.support.expect import raises_with
from tests.support.ids import MISSING_ID
from tests.unit.application.action_env import ACTION_OR_NEXT_REQUIRED, KIM, SUMMARY

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv

NUL = "Comment에는 NUL 문자를 쓸 수 없습니다"


async def _all_comments(action_env: ActionEnv) -> list[tuple[DealActionId | None, str]]:
    found = await action_env.env.uow.deal_comments.list_for_deal(action_env.deal.item.deal.id)
    return [(c.action_id, c.body) for c in found]


async def test_registering_with_a_comment_creates_the_action_comment_and_orders_the_history(
    action_env: ActionEnv,
) -> None:
    """comment와 함께 등록하면 새 Action의 Action Comment가 생기고 이력은 Action 등록 다음
    Comment 등록이며 시각이 같고 커밋은 1번이다.

    테스트 코드: CM-026
    """
    # given: 커밋 횟수
    commits = action_env.env.uow.commits

    # when: KIM이 comment "  요구사항 정리  "로 Action을 등록한다
    action = await action_env.act(KIM, comment="  요구사항 정리  ")

    # then: 응답 Action 내용에 memo가 없다
    assert not hasattr(action.content, "memo")
    # then: 그 Action에 연결된 Comment 1건이 생긴다(본문 trim, 작성자 KIM, 시각은 요청 시각)
    (comment,) = await action_env.env.uow.deal_comments.list_for_deal(action.deal_code)
    assert comment.action_id == action.id
    assert (comment.body, comment.author_user_id) == ("요구사항 정리", KIM.user_id)
    assert comment.created_at == comment.updated_at == action_env.env.clock.now()
    # then: 이력은 Action 등록 줄 다음에 Comment 등록 줄이고 같은 시각이다
    assert await action_env.rows() == [
        ("action", "Action", "", f"등록: {SUMMARY}"),
        (
            "comment",
            f"Action Comment ({action.acted_on.isoformat()} 미팅)",
            "",
            "등록: 요구사항 정리",
        ),
    ]
    entries = (await action_env.entries())[-2:]
    assert entries[0].changed_at == entries[1].changed_at == action_env.env.clock.now()
    # then: 커밋은 1번이다
    assert action_env.env.uow.commits == commits + 1


async def test_the_comment_target_uses_the_new_actions_acted_on_date(
    action_env: ActionEnv,
) -> None:
    """이력 대상의 수행일은 새 Action의 수행일이다(요청일과 다를 수 있다).

    테스트 코드: CM-026
    """
    # given: Deal 등록 5일 뒤 시점에서 2일 전(등록일 이후) 수행일
    action_env.env.clock.advance(5 * 86400)
    acted_on = action_env.env.clock.now().astimezone().date() - timedelta(days=2)
    action_env.env.clock.advance(1)

    # when: 수행일을 지정해 comment와 함께 등록한다
    await action_env.act(KIM, acted_on=acted_on, comment="지난 일")

    # then: Comment 등록 줄 대상에 그 수행일이 들어 있다
    assert (await action_env.rows())[-1][1] == f"Action Comment ({acted_on.isoformat()} 미팅)"


@pytest.mark.parametrize("comment", [None, "", "  \n "], ids=["omitted", "empty", "blank"])
async def test_no_comment_is_made_for_an_omitted_empty_or_blank_comment(
    action_env: ActionEnv, comment: str | None
) -> None:
    """comment를 생략·비움·공백만 보내면 Comment가 없고 이력에는 Action 등록 줄만 늘어난다.

    테스트 코드: CM-027
    """
    # when: comment 없이/빈 값/공백만으로 등록한다
    if comment is None:
        await action_env.act(KIM)
    else:
        await action_env.act(KIM, comment=comment)

    # then: 등록은 성공했고 Comment는 없으며 이력은 Action 등록 줄뿐이다
    assert await _all_comments(action_env) == []
    assert await action_env.rows() == [("action", "Action", "", f"등록: {SUMMARY}")]


@pytest.mark.parametrize(
    ("kind", "kwargs", "message"),
    [
        pytest.param(
            "content",
            {"action": "", "next_action": "", "due_date": None},
            ACTION_OR_NEXT_REQUIRED,
            id="content-error-first",
        ),
        pytest.param("nul", {}, NUL, id="nul-before-the-acted-on-check"),
    ],
)
async def test_the_comment_check_comes_after_content_and_before_the_acted_on_check(
    action_env: ActionEnv, kind: str, kwargs: dict[str, Any], message: str
) -> None:
    """comment NUL은 내용 오류 다음, 수행일 오류 앞에서 판정되고 아무것도 남지 않는다.

    테스트 코드: CM-028
    """
    # given: 내일 수행일(미래 수행일은 별도 422다)과 NUL이 든 comment
    tomorrow = action_env.env.clock.now().astimezone().date() + timedelta(days=1)
    commits = action_env.env.uow.commits

    # when·then: 내용 오류가 있으면 그 문구, 없으면 Comment NUL 문구로 거절된다
    with raises_with(InvalidValueError, message):
        await action_env.act(KIM, comment="가\x00나", acted_on=tomorrow, **kwargs)

    # then: Action·Comment·이력·커밋이 그대로다
    assert len(action_env.env.uow.deal_actions._items) == 0
    assert await _all_comments(action_env) == []
    assert await action_env.rows() == []
    assert action_env.env.uow.commits == commits


async def test_a_comment_with_nul_does_not_create_the_new_action_type(
    action_env: ActionEnv,
) -> None:
    """NUL이 든 comment 때문에 거절되면 새 유형 "웨비나"도 만들어지지 않는다.

    테스트 코드: CM-028
    """
    # given: 새 유형 이름과 NUL이 든 comment
    from app.application.choice import CatalogChoice  # noqa: PLC0415

    before = {t.name for t in await action_env.env.uow.action_types.list()}

    # when·then: 등록하면 Comment NUL 문구로 거절된다
    with raises_with(InvalidValueError, NUL):
        await action_env.act(KIM, action_type=CatalogChoice(name="웨비나"), comment="가\x00나")

    # then: 유형 목록이 그대로다
    assert {t.name for t in await action_env.env.uow.action_types.list()} == before
    assert "웨비나" not in before


async def test_a_rejected_registration_leaves_no_comment(action_env: ActionEnv) -> None:
    """등록이 다른 이유(이전 Next Action 기준 행 불일치 409)로 거절되면 Comment도 남지 않는다.

    테스트 코드: CM-029
    """
    # given: Deal D의 기준 행 A와 다른 Deal의 Action B
    await action_env.act(KIM)
    other = await action_env.env.new_deal()
    foreign = await action_env.act(KIM, code=other.item.deal.id.value)
    rows = await action_env.rows()
    comments = await _all_comments(action_env)
    action_count = len(action_env.env.uow.deal_actions._items)

    # when·then: B를 이전 Next Action으로 닫도록 지정해 comment와 등록하면 409다
    with pytest.raises(InvalidStateError):
        await action_env.act(KIM, close_previous=foreign.id, comment="메모")
    with pytest.raises(InvalidStateError):
        await action_env.act(KIM, close_previous=DealActionId(MISSING_ID), comment="메모")

    # then: Action·Comment·이력이 그대로다
    assert len(action_env.env.uow.deal_actions._items) == action_count
    assert await _all_comments(action_env) == comments
    assert await action_env.rows() == rows


async def test_closing_the_previous_next_action_by_registering_makes_no_comment(
    action_env: ActionEnv,
) -> None:
    """등록하며 이전 Next Action을 종료(수행)로 닫아도 그 종료는 Comment를 만들지 않는다.

    테스트 코드: CM-015, CM-026
    """
    # given: 기준 행
    previous = await action_env.act(KIM)

    # when: comment 없이 이전 Next Action을 닫으며 등록한다
    await action_env.act(KIM, close_previous=previous.id, next_action="다음 일정")

    # then: Comment가 없다
    assert await _all_comments(action_env) == []
