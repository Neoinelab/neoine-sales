"""Deal 화면 값의 기준 행: overdue는 Next Action 기준 행, stale은 모든 Action 기준.

"오늘"은 서버 시계를 Asia/Seoul 날짜로 바꾼 값이다(FixedClock 시작 01-01 18:00).
"""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_repository import DealQuery, NextActionSummary
from app.domain.deal.risk import Risk
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealView
    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.deal_env import DealEnv

DAY = 24 * 3600


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _act(env: DealEnv, view: DealView, **content: Any) -> DealAction:  # noqa: ANN401
    action = make_deal_action(
        deal_code=view.item.deal.id,
        acted_at=env.clock.now(),
        actor_user_id=ACTOR_ID,
        **content,
    )
    await env.uow.deal_actions.add(action)
    return action


async def _listed(env: DealEnv, code: str) -> DealView:
    (row,) = (await env.list.execute(DealQuery(keyword=code))).items
    return row


async def test_closed_next_action_keeps_overdue(env: DealEnv) -> None:
    """기한이 지난 Next Action을 종료해도 기한초과가 유지된다.

    테스트 코드: RK-013
    """
    # given: Due가 어제 지난 Next Action이 있는 Deal이다
    view = await env.new_deal()
    action = await _act(env, view, due_date=date(2026, 1, 2))
    env.clock.advance(2 * DAY)  # 오늘 = 01-03
    action.change_next_action_status(NextActionStatus.DONE, "", env.clock.now())
    # when: 2일 뒤 Next Action을 done으로 바꾸고 조회한다
    await env.uow.deal_actions.update(action)

    code = view.item.deal.id.value

    # then: 목록과 상세 모두 risk가 overdue다
    assert (await env.get.execute(code)).risk is Risk.OVERDUE
    assert (await _listed(env, code)).risk is Risk.OVERDUE


async def test_overdue_uses_the_latest_row_that_has_a_next_action(env: DealEnv) -> None:
    """더 최근에 진행사항만 Action이 있어도 기준 행의 Due로 기한초과를 판정한다.

    테스트 코드: RK-012
    """
    # given: Due가 01-02인 Action 뒤에 진행사항만 Action이 등록되었다
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    env.clock.advance(60)
    await _act(env, view, action="통화만", next_action="")  # 더 최근이지만 Next Action이 없다
    env.clock.advance(2 * DAY)  # 오늘 = 01-03

    # when: 2일 뒤(01-03) 상세를 조회한다
    detail = await env.get.execute(view.item.deal.id.value)

    # then: risk는 overdue이고 next_action의 Due는 01-02다
    assert detail.risk is Risk.OVERDUE
    assert detail.item.next_action is not None
    assert detail.item.next_action.due_date == date(2026, 1, 2)


async def test_deal_with_only_progress_only_actions_is_never_overdue(env: DealEnv) -> None:
    """진행사항만 Action만 있으면 next_action이 없어 기한초과가 아니다.

    테스트 코드: RK-003
    """
    # given: 진행사항만 Action만 있는 Deal이 5일 지났다
    view = await env.new_deal()
    await _act(env, view, action="통화만", next_action="")
    env.clock.advance(5 * DAY)

    # when: 상세를 조회한다
    risk = (await env.get.execute(view.item.deal.id.value)).risk
    # then: risk가 없다
    assert risk is None


async def test_progress_only_action_refreshes_stale(env: DealEnv) -> None:
    """진행사항만 Action을 등록하면 미업데이트가 풀리고 14일이 다시 지나면 미업데이트다.

    테스트 코드: RK-020
    """
    # given: 13일째에 진행사항만 Action을 등록한 Deal이다
    view = await env.new_deal()
    code = view.item.deal.id.value
    env.clock.advance(13 * DAY)
    registered = await _act(env, view, action="통화만", next_action="")  # 진행사항만 등록
    env.clock.advance(13 * DAY)  # 등록 후 13일: 기준 14일 미만

    # when: Action 등록 13일 뒤 상세를 조회한다
    detail = await env.get.execute(code)

    # then: risk는 없고 최종 업데이트는 그 Action 수행 시각이며, 하루 더 지나면 stale이다
    assert detail.risk is None
    assert detail.item.last_updated_at == registered.acted_at
    env.clock.advance(1 * DAY)
    assert (await env.get.execute(code)).risk is Risk.STALE


async def test_stale_ignores_the_status_of_the_next_action(env: DealEnv) -> None:
    """Next Action 상태는 미업데이트 판정에 영향이 없다.

    테스트 코드: RK-019
    """
    # given: Next Action을 done으로 종료한 Action이 있는 Deal이다
    view = await env.new_deal()
    code = view.item.deal.id.value
    action = await _act(env, view, due_date=date(2026, 3, 1))
    action.change_next_action_status(NextActionStatus.DONE, "", env.clock.now())
    await env.uow.deal_actions.update(action)
    # when: 14일이 지난 뒤 상세를 조회한다
    env.clock.advance(14 * DAY)

    # then: risk가 stale이다
    assert (await env.get.execute(code)).risk is Risk.STALE


async def test_a_later_progress_only_action_does_not_replace_the_next_action(
    env: DealEnv,
) -> None:
    """더 최근의 진행사항만 Action은 Next Action 기준 행을 대신하지 않는다.

    테스트 코드: RK-001
    """
    # given: Next Action "계약서 검토"(Due 오늘+30일) 뒤에 진행사항만 Action이 등록되었다
    view = await env.new_deal()
    code = view.item.deal.id.value
    due = date(2026, 1, 31)
    await _act(env, view, next_action="계약서 검토", due_date=due)
    env.clock.advance(60)
    await _act(env, view, action="전화 통화", next_action="")

    # when: 목록과 상세를 조회한다
    listed = await _listed(env, code)
    detail = await env.get.execute(code)

    # then: 두 응답의 next_action은 계약서 검토 / 오늘+30일 / open이다
    expected = NextActionSummary(text="계약서 검토", due_date=due, status=NextActionStatus.OPEN)
    assert listed.item.next_action == expected
    assert detail.item.next_action == expected


async def test_equal_acted_at_makes_the_larger_id_the_next_action_basis(env: DealEnv) -> None:
    """수행 시각이 같으면 id가 큰 Action이 Next Action 기준 행이다.

    테스트 코드: RK-002
    """
    # given: 같은 수행 시각의 Next Action 두 건(id가 큰 "나중"을 먼저 저장한다)
    view = await env.new_deal()
    await _act(env, view, next_action="나중", entity_id=DealActionId(2_000))
    await _act(env, view, next_action="먼저", entity_id=DealActionId(1_000))

    # when: 상세를 조회한다
    detail = await env.get.execute(view.item.deal.id.value)

    # then: next_action.text는 id가 큰 "나중"이다
    assert detail.item.next_action is not None
    assert detail.item.next_action.text == "나중"


async def test_a_progress_only_action_frees_the_deal_from_stale_until_the_limit_passes_again(
    env: DealEnv,
) -> None:
    """진행사항만 Action이 미업데이트를 풀고 기준일이 다시 지나면 미업데이트다.

    테스트 코드: RK-020
    """
    # given: Action 없이 13일이 지난 Deal에 진행사항만 Action을 등록했다
    view = await env.new_deal()
    code = view.item.deal.id.value
    env.clock.advance(13 * DAY)
    registered = await _act(env, view, action="통화만", next_action="")

    # when: 하루 뒤(Deal 등록 14일째)에 조회한다
    env.clock.advance(DAY)
    freed = await env.get.execute(code)

    # then: 최종 업데이트는 그 Action 수행 시각이고 경고가 없다
    assert freed.item.last_updated_at == registered.acted_at
    assert freed.risk is None

    # when: Action 수행 14일째에 다시 조회한다
    env.clock.advance(13 * DAY)

    # then: 다시 미업데이트다
    assert (await env.get.execute(code)).risk is Risk.STALE
