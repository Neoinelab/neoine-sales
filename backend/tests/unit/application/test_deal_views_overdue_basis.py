"""Deal 화면 값의 Next Action 기준 행(RK-R1): 지난 Open Next Action이 있으면 Due가 가장 이른 행.

"오늘"은 서버 시계(FixedClock)를 Asia/Seoul 날짜로 바꾼 값이다. FixedClock의 시작(2026-01-01
09:00Z)은 Seoul 01-01 18:00이고, `_today(env, 2026-01-10)`이 하루 단위로 시계를 맞춘다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import DealChangeInput
from app.application.ports.deal_repository import DealQuery, NextActionSummary
from app.domain.deal.risk import Risk
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action
from tests.factories_deal import SALES, make_patch
from tests.support.user_ids import ACTOR_ID
from tests.unit.application.apply_helpers import CLOSING

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealView
    from app.domain.deal_action.entities import DealAction
    from tests.unit.application.deal_env import DealEnv

DAY = 24 * 3600
START = date(2026, 1, 1)  # FixedClock 시작의 업무 날짜(Seoul)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _today(env: DealEnv, day: date) -> None:
    """서버 시계를 그 업무 날짜(같은 18:00)로 맞춘다."""
    env.clock.advance((day - env.clock.now().astimezone().date()).days * DAY)


async def _act(  # noqa: PLR0913 - 행 하나를 정하는 독립된 값들
    env: DealEnv,
    view: DealView,
    row_id: int,
    *,
    acted_on: date,
    text: str,
    due: date,
) -> DealAction:
    """저장소에 직접 둔 Next Action 행(id를 정해 "id가 큰 행"을 통제한다)."""
    action = make_deal_action(
        deal_code=view.item.deal.id,
        now=env.clock.now(),
        actor_user_id=ACTOR_ID,
        acted_on=acted_on,
        entity_id=DealActionId(row_id),
        next_action=text,
        due_date=due,
    )
    await env.uow.deal_actions.add(action)
    return action


async def _save(env: DealEnv, action: DealAction) -> None:
    await env.uow.deal_actions.update(action)


async def _listed(env: DealEnv, code: str) -> DealView:
    (row,) = (await env.list.execute(DealQuery(keyword=code))).items
    return row


def _summary(action: DealAction) -> NextActionSummary:
    assert action.content.next_action is not None
    assert action.content.due_date is not None
    assert action.next_action_state is not None
    return NextActionSummary(
        text=action.content.next_action,
        due_date=action.content.due_date,
        status=action.next_action_state.status,
        action_id=action.id,
    )


async def _three_row_deal(env: DealEnv) -> tuple[DealView, DealAction, DealAction, DealAction]:
    """RK-080의 Deal: A(Due 01-06), B(Due 01-04), C(Due 01-20), 모두 Open. 오늘 2026-01-10."""
    view = await env.new_deal()
    a = await _act(
        env, view, 101, acted_on=date(2026, 1, 1), text="견적 발송", due=date(2026, 1, 6)
    )
    b = await _act(env, view, 102, acted_on=date(2026, 1, 3), text="제안서", due=date(2026, 1, 4))
    c = await _act(env, view, 103, acted_on=date(2026, 1, 9), text="데모", due=date(2026, 1, 20))
    _today(env, date(2026, 1, 10))
    return view, a, b, c


async def test_overdue_deal_shows_the_earliest_due_past_open_row_in_list_and_detail(
    env: DealEnv,
) -> None:
    """기한초과 Deal의 next_action은 지난 Open 중 Due가 가장 이른 행이고 목록·상세가 같다.

    테스트 코드: RK-080
    """
    # given: 오늘이 01-10이고 Open Next Action이 A(Due 01-06)·B(Due 01-04)·C(Due 01-20)다
    view, _, b, _ = await _three_row_deal(env)
    code = view.item.deal.id.value

    # when: 목록과 상세를 조회한다
    detail = await env.get.execute(code)
    listed = await _listed(env, code)

    # then: 둘 다 기한초과이고 next_action은 Due가 가장 이른 B다(action_id 포함)
    for shown in (detail, listed):
        assert shown.risk is Risk.OVERDUE
        assert shown.item.next_action == _summary(b)
        assert shown.item.next_action is not None
        assert shown.item.next_action.action_id == b.id


async def test_equal_past_due_picks_the_larger_id_and_ignores_acted_on(env: DealEnv) -> None:
    """지난 Open의 Due가 같으면 id가 큰 행이고 수행일은 보지 않는다.

    테스트 코드: RK-081
    """
    # given: Due 01-05가 같은 A(id 작음, 수행일 늦음)·B(id 큼, 수행일이 빠름)와 미래 Due의 C
    view = await env.new_deal()
    await _act(env, view, 201, acted_on=date(2026, 1, 8), text="가", due=date(2026, 1, 5))
    b = await _act(env, view, 202, acted_on=date(2026, 1, 2), text="나", due=date(2026, 1, 5))
    await _act(env, view, 203, acted_on=date(2026, 1, 9), text="다", due=date(2026, 1, 30))
    _today(env, date(2026, 1, 10))

    # when: 상세를 조회한다
    detail = await env.get.execute(view.item.deal.id.value)

    # then: next_action은 id가 큰 B다(수행일이 더 늦은 A가 아니다)
    assert detail.item.next_action is not None
    assert detail.item.next_action.text == "나"
    assert detail.item.next_action.action_id == b.id


async def test_closing_past_open_rows_returns_to_latest_and_reopening_brings_one_back(
    env: DealEnv,
) -> None:
    """지난 Open을 모두 종료하면 가장 최근 행이고, 하나를 Open으로 되돌리면 그 행이 된다.

    테스트 코드: RK-082
    """
    # given: RK-080과 같은 Deal(오늘 01-10)
    view, a, b, c = await _three_row_deal(env)
    code = view.item.deal.id.value

    # when: B를 done, A를 not_done으로 종료한 뒤 상세를 조회한다
    b.change_next_action_status(NextActionStatus.DONE, "", env.clock.now())
    a.change_next_action_status(NextActionStatus.NOT_DONE, "", env.clock.now())
    await _save(env, b)
    await _save(env, a)
    closed = await env.get.execute(code)

    # then: next_action은 가장 최근 행 C(open)이고 risk는 없다
    assert closed.item.next_action == _summary(c)
    assert closed.item.next_action is not None
    assert closed.item.next_action.text == "데모"
    assert closed.risk is None

    # when: A를 Open으로 되돌린 뒤 다시 조회한다
    a.change_next_action_status(NextActionStatus.OPEN, "", env.clock.now())
    await _save(env, a)
    reopened = await env.get.execute(code)

    # then: next_action은 A(Due 01-06)이고 기한초과다
    assert reopened.item.next_action == _summary(a)
    assert reopened.item.next_action is not None
    assert reopened.item.next_action.due_date == date(2026, 1, 6)
    assert reopened.risk is Risk.OVERDUE


async def test_due_today_is_not_past_and_becomes_the_basis_the_next_day(env: DealEnv) -> None:
    """Due가 오늘인 Open 행은 지난 행이 아니고 다음 날 요청부터 기준 행이 된다.

    테스트 코드: RK-083
    """
    # given: A(Due 01-10 Open)와 그 뒤 B(Due 01-30, done)
    view = await env.new_deal()
    code = view.item.deal.id.value
    a = await _act(env, view, 301, acted_on=date(2026, 1, 2), text="견적", due=date(2026, 1, 10))
    b = await _act(env, view, 302, acted_on=date(2026, 1, 9), text="데모", due=date(2026, 1, 30))
    b.change_next_action_status(NextActionStatus.DONE, "", env.clock.now())
    await _save(env, b)

    # when: 업무 날짜 01-10에 조회하고, 데이터는 그대로 두고 01-11에 다시 조회한다
    _today(env, date(2026, 1, 10))
    on_the_day = await env.get.execute(code)
    _today(env, date(2026, 1, 11))
    next_day = await env.get.execute(code)

    # then: 01-10에는 B(done)이고 기한초과가 아니다
    assert on_the_day.item.next_action == _summary(b)
    assert on_the_day.item.next_action is not None
    assert on_the_day.item.next_action.status is NextActionStatus.DONE
    assert on_the_day.risk not in (Risk.OVERDUE, Risk.OVERDUE_STALE)
    # then: 01-11에는 A(Due 01-10, open)이고 기한초과가 포함된다
    assert next_day.item.next_action == _summary(a)
    assert next_day.risk in (Risk.OVERDUE, Risk.OVERDUE_STALE)


@pytest.mark.parametrize("forecast_key", ["won", "lost"])
async def test_closed_deal_shows_the_past_open_row_and_has_no_risk(
    env: DealEnv, forecast_key: str
) -> None:
    """종결(Won·Lost) Deal도 지난 Open Next Action이 있으면 그 행을 보이고 risk는 null이다.

    테스트 코드: RK-084
    """
    # given: A(Due 01-05, Open)와 그 뒤 B(Due 01-20, done)가 있는 Deal을 Won 또는 Lost로 닫았다
    view = await env.new_deal(status_key="price_negotiation", forecast_key="pipeline")
    code = view.item.deal.id.value
    a = await _act(
        env, view, 401, acted_on=date(2026, 1, 1), text="후속 연락", due=date(2026, 1, 5)
    )
    b = await _act(
        env, view, 402, acted_on=date(2026, 1, 9), text="감사 메일", due=date(2026, 1, 20)
    )
    b.change_next_action_status(NextActionStatus.DONE, "", env.clock.now())
    await _save(env, b)
    if forecast_key == "won":
        change = DealChangeInput(field="forecast_key", value="won", resolution=CLOSING)
        await env.apply.execute(code, change, SALES)
    else:
        await env.update.execute(code, make_patch(forecast_key="lost"), SALES)
    _today(env, date(2026, 1, 10))

    # when: 목록과 상세를 조회한다
    detail = await env.get.execute(code)
    listed = await _listed(env, code)

    # then: 둘 다 next_action은 A(open)이고 risk는 null이다
    for shown in (detail, listed):
        assert shown.item.next_action == _summary(a)
        assert shown.risk is None
