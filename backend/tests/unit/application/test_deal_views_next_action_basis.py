"""Deal 화면 값의 기준 행(AC-15·16·17): overdue는 Next Action 기준 행, stale은 모든 Action 기준.

"오늘"은 서버 시계를 Asia/Seoul 날짜로 바꾼 값이다(FixedClock 시작 01-01 18:00).
"""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.deal.risk import Risk
from app.domain.deal_action.next_action_status import NextActionStatus
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
    view = await env.new_deal()
    action = await _act(env, view, due_date=date(2026, 1, 2))
    env.clock.advance(2 * DAY)  # 오늘 = 01-03
    action.change_next_action_status(NextActionStatus.DONE, "", env.clock.now())
    await env.uow.deal_actions.update(action)

    code = view.item.deal.id.value

    assert (await env.get.execute(code)).risk is Risk.OVERDUE
    assert (await _listed(env, code)).risk is Risk.OVERDUE


async def test_overdue_uses_the_latest_row_that_has_a_next_action(env: DealEnv) -> None:
    view = await env.new_deal()
    await _act(env, view, due_date=date(2026, 1, 2))
    env.clock.advance(60)
    await _act(env, view, action="통화만", next_action="")  # 더 최근이지만 Next Action이 없다
    env.clock.advance(2 * DAY)  # 오늘 = 01-03

    detail = await env.get.execute(view.item.deal.id.value)

    assert detail.risk is Risk.OVERDUE
    assert detail.item.next_action is not None
    assert detail.item.next_action.due_date == date(2026, 1, 2)


async def test_deal_with_only_progress_only_actions_is_never_overdue(env: DealEnv) -> None:
    view = await env.new_deal()
    await _act(env, view, action="통화만", next_action="")
    env.clock.advance(5 * DAY)

    assert (await env.get.execute(view.item.deal.id.value)).risk is None


async def test_progress_only_action_refreshes_stale(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    env.clock.advance(13 * DAY)
    registered = await _act(env, view, action="통화만", next_action="")  # 진행사항만 등록
    env.clock.advance(13 * DAY)  # 등록 후 13일: 기준 14일 미만

    detail = await env.get.execute(code)

    assert detail.risk is None
    assert detail.item.last_updated_at == registered.acted_at
    env.clock.advance(1 * DAY)
    assert (await env.get.execute(code)).risk is Risk.STALE


async def test_stale_ignores_the_status_of_the_next_action(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    action = await _act(env, view, due_date=date(2026, 3, 1))
    action.change_next_action_status(NextActionStatus.DONE, "", env.clock.now())
    await env.uow.deal_actions.update(action)
    env.clock.advance(14 * DAY)

    assert (await env.get.execute(code)).risk is Risk.STALE
