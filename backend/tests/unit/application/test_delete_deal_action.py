"""DeleteDealAction: 담당자 본인과 admin만, 물리 삭제와 이력, 판정 순서 404 -> 403."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import NextActionSummary
from app.domain.deal_action.errors import (
    DealActionDeleteForbiddenError,
    DealActionNotFoundError,
)
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.action_env import (
    BOSS,
    DELETE_FORBIDDEN,
    KIM,
    NOT_FOUND,
    PARK,
    SUMMARY,
    VIEWER,
)

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv


async def test_delete_action_by_owner_logs_history_and_removes_the_row(
    action_env: ActionEnv,
) -> None:
    """담당자가 지우면 행이 사라지고 요약과 "삭제" 이력이 남는다.

    테스트 코드: AC-059
    """
    # given: KIM이 남긴 기본 Action
    action = await action_env.act(KIM)

    # when: KIM이 Action을 지운다
    await action_env.delete.execute(action.id, KIM)

    # then: 그 id의 Action이 없다
    with pytest.raises(DealActionNotFoundError):
        await action_env.stored(action.id)
    # then: 이력 최신 줄은 삭제 전 요약과 "삭제"이고 변경자는 KIM이다
    assert (await action_env.rows())[-1] == ("action", "Action", SUMMARY, "삭제")
    assert (await action_env.action_entries())[-1].changed_by == KIM.user_id


async def test_deleting_an_action_removes_only_its_comments_and_counts_them_in_the_history(
    action_env: ActionEnv,
) -> None:
    """Action을 지우면 그 Action Comment만 함께 지워지고 이력에 함께 지운 건수가 붙는다.

    테스트 코드: CM-037
    """
    # given: A에 Action Comment 2건, Deal Comment 1건, 다른 Action A2에 Comment 1건, Comment 없는 A3
    from tests.factories_comment import make_comment  # noqa: PLC0415

    action = await action_env.act(KIM)
    second = await action_env.act(KIM)
    third = await action_env.act(KIM)
    comments = action_env.env.uow.deal_comments
    code = action.deal_code
    for linked, body in ((action.id, "a1"), (action.id, "a2"), (None, "deal"), (second.id, "b1")):
        await comments.add(
            make_comment(deal_code=code, action_id=linked, body=body, author=KIM.user_id)
        )
    summary = SUMMARY

    # when: KIM이 A를 지우고 이어서 A3을 지운다
    await action_env.delete.execute(action.id, KIM)
    await action_env.delete.execute(third.id, KIM)

    # then: A의 Comment 2건만 없어지고 Deal Comment·A2의 Comment는 그대로다
    assert sorted(c.body for c in await comments.list_for_deal(code)) == ["b1", "deal"]
    # then: A 삭제 줄은 "삭제 (Comment 2건 함께 삭제)", A3 삭제 줄은 "삭제"이고 Comment별 줄은 없다
    delete_rows = [row for row in await action_env.rows() if row[3].startswith("삭제")]
    assert [row[2:] for row in delete_rows] == [
        (summary, "삭제 (Comment 2건 함께 삭제)"),
        (summary, "삭제"),
    ]
    assert [row for row in await action_env.rows() if row[0] == "comment"] == []


async def test_delete_action_by_owner_logs_history_and_next_action_falls_back(
    action_env: ActionEnv,
) -> None:
    """가장 최근 Action을 지우면 Deal의 Next Action이 이전 Action으로 돌아간다.

    테스트 코드: AC-060
    """
    # given: "먼저 할 일" Action 뒤에 "나중 할 일" Action
    await action_env.act(KIM, next_action="먼저 할 일", due_date=date(2026, 3, 1))
    latest = await action_env.act(KIM, next_action="나중 할 일", due_date=date(2026, 4, 1))

    # when: 나중 Action을 지운다
    await action_env.delete.execute(latest.id, KIM)

    # then: Deal Next Action은 "먼저 할 일"이다
    detail = await action_env.env.get.execute(action_env.code)
    assert detail.item.next_action == NextActionSummary(
        "먼저 할 일", date(2026, 3, 1), NextActionStatus.OPEN
    )


async def test_deleting_the_only_action_leaves_the_deal_without_a_next_action(
    action_env: ActionEnv,
) -> None:
    """하나뿐인 Action을 지우면 Deal의 Next Action은 없다.

    테스트 코드: AC-060
    """
    # given: Action이 하나뿐인 Deal
    action = await action_env.act(KIM)

    # when: 그 Action을 지운다
    await action_env.delete.execute(action.id, KIM)

    # then: Deal Next Action이 없다
    assert (await action_env.env.get.execute(action_env.code)).item.next_action is None


async def test_delete_action_by_admin_removes_another_users_action(action_env: ActionEnv) -> None:
    """admin이 남의 Action을 지우면 이력 변경자는 admin이다.

    테스트 코드: AC-061
    """
    # given: KIM이 남긴 Action
    action = await action_env.act(KIM)

    # when: admin이 지운다
    await action_env.delete.execute(action.id, BOSS)

    # then: Action이 사라진다
    with pytest.raises(DealActionNotFoundError):
        await action_env.stored(action.id)
    # then: 이력 변경자는 admin이다
    assert (await action_env.action_entries())[-1].changed_by == BOSS.user_id


async def test_delete_action_by_other_sales_is_forbidden_and_keeps_action(
    action_env: ActionEnv,
) -> None:
    """다른 sales의 삭제는 403이고 Action·이력이 그대로다.

    테스트 코드: AC-062
    """
    # given: KIM이 남긴 Action과 삭제 전 이력
    action = await action_env.act(KIM)
    rows_before = await action_env.rows()

    # when·then: 다른 sales가 지우면 삭제 권한 오류다
    with raises_with(DealActionDeleteForbiddenError, DELETE_FORBIDDEN):
        await action_env.delete.execute(action.id, PARK)

    # then: Action과 이력이 그대로다
    assert (await action_env.stored(action.id)).content == action.content
    assert await action_env.rows() == rows_before


async def test_delete_action_by_a_read_only_user_is_forbidden_even_for_own_id(
    action_env: ActionEnv,
) -> None:
    """읽기 전용 user는 자기 id의 Action도 지울 수 없다.

    테스트 코드: AC-064
    """
    # given: user가 담당자로 된 Action
    own = make_deal_action(deal_code=action_env.deal.item.deal.id, actor_user_id=VIEWER.user_id)
    await action_env.env.uow.deal_actions.add(own)

    # when·then: user가 지우면 삭제 권한 오류다
    with pytest.raises(DealActionDeleteForbiddenError):
        await action_env.delete.execute(own.id, VIEWER)

    # then: Action이 그대로 있다
    assert (await action_env.stored(own.id)).id == own.id


async def test_delete_missing_action_is_not_found_whoever_asks(action_env: ActionEnv) -> None:
    """없는 Action의 삭제는 누가 해도 404다.

    테스트 코드: AC-063
    """
    # given: 존재하지 않는 Action id
    missing = DealActionId(new_id())

    for actor in (KIM, PARK, BOSS):
        # when·then: 어느 역할이 지워도 Action 없음 오류다
        with raises_with(DealActionNotFoundError, NOT_FOUND):
            await action_env.delete.execute(missing, actor)


async def test_deleting_the_action_twice_is_not_found_the_second_time(
    action_env: ActionEnv,
) -> None:
    """이미 지운 Action을 다시 지우면 404다.

    테스트 코드: AC-063
    """
    # given: KIM이 이미 지운 Action
    action = await action_env.act(KIM)
    await action_env.delete.execute(action.id, KIM)

    # when·then: 같은 Action을 다시 지우면 Action 없음 오류다
    with raises_with(DealActionNotFoundError, NOT_FOUND):
        await action_env.delete.execute(action.id, KIM)


async def test_delete_clips_the_history_summary_but_the_row_is_removed(
    action_env: ActionEnv,
) -> None:
    """긴 요약은 삭제 이력의 변경 전만 1,000자로 자른다.

    테스트 코드: AC-059
    """
    # given: 진행사항 3,000자인 Action
    action = await action_env.act(KIM, action="가" * 3_000)

    # when: 그 Action을 지운다
    await action_env.delete.execute(action.id, KIM)

    # then: 이력 변경 전은 1,000자에서 "…"로 끝나고 변경 후는 "삭제"다
    (_, _, before, after) = (await action_env.rows())[-1]
    assert (len(before), after) == (1_000, "삭제")
    assert before.endswith("…")
