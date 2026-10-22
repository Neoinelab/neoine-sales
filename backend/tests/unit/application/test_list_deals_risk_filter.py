"""ListDeals의 기한초과·미업데이트 필터(AC-10, T-7~T-9).

유스케이스가 서버 업무 날짜와 저장된 경고 기준(없으면 14일)으로 판정 기준을 만들고, 필터 결과와
각 행의 risk, 전체 건수가 일치하는지를 본다. 저장소 계약은 tests/unit/repositories가 따로 본다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.alert.thresholds import AlertThresholds
from app.domain.deal.risk import Risk
from tests.factories import make_deal_action
from tests.factories_deal import SALES, make_patch
from tests.support.user_ids import ACTOR_ID, OWNER_ID

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealPage, DealView
    from tests.unit.application.deal_env import DealEnv

DAY = 24 * 3600


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")  # FixedClock 시작(2026-01-01 09:00Z) = Seoul 01-01 18:00


async def _save_threshold(env: DealEnv, days: int) -> None:
    async with env.uow_factory() as uow:
        await uow.alert_settings.save(
            AlertThresholds(stale_days=days), updated_by=OWNER_ID, now=env.clock.now()
        )
        await uow.commit()


async def _act(env: DealEnv, view: DealView, *, due_date: date) -> None:
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=view.item.deal.id,
            acted_at=env.clock.now(),
            actor_user_id=ACTOR_ID,
            due_date=due_date,
        )
    )


def _codes(page: DealPage) -> set[str]:
    return {view.item.deal.id.value for view in page.items}


def _code(view: DealView) -> str:
    return view.item.deal.id.value


async def test_list_uses_the_business_today_and_the_saved_stale_days(env: DealEnv) -> None:
    await _save_threshold(env, 7)
    old = await env.new_deal()
    env.clock.advance(7 * DAY)  # 오늘 = 01-08, 마지막 갱신 01-01 -> 7일 경과

    page = await env.list.execute(DealQuery(stale=True))

    assert _codes(page) == {_code(old)}
    assert page.items[0].risk is Risk.STALE


async def test_list_does_not_flag_a_deal_one_day_short_of_the_saved_stale_days(
    env: DealEnv,
) -> None:
    await _save_threshold(env, 7)
    await env.new_deal()
    env.clock.advance(6 * DAY)

    page = await env.list.execute(DealQuery(stale=True))

    assert (page.items, page.total) == ([], 0)


async def test_list_uses_the_default_stale_days_when_nothing_is_saved(env: DealEnv) -> None:
    old = await env.new_deal()
    env.clock.advance(13 * DAY)
    assert (await env.list.execute(DealQuery(stale=True))).total == 0

    env.clock.advance(DAY)  # 14일 경과

    page = await env.list.execute(DealQuery(stale=True))
    assert _codes(page) == {_code(old)}


async def _five_deals(env: DealEnv) -> dict[str, DealView]:
    """경고 기준 7일, 오늘 = 01-09. stale만 / 둘 다 / Lost / overdue만 / 없음."""
    await _save_threshold(env, 7)
    deals: dict[str, DealView] = {}
    deals["stale_only"] = await env.new_deal(name="stale only")
    deals["both"] = await env.new_deal(name="both")
    await _act(env, deals["both"], due_date=date(2026, 1, 2))
    deals["closed"] = await env.new_deal(name="closed", forecast_key="pipeline")
    await _act(env, deals["closed"], due_date=date(2026, 1, 2))
    await env.update.execute(_code(deals["closed"]), make_patch(forecast_key="lost"), SALES)
    env.clock.advance(8 * DAY)
    deals["overdue_only"] = await env.new_deal(name="overdue only")
    await _act(env, deals["overdue_only"], due_date=date(2026, 1, 5))
    deals["fresh"] = await env.new_deal(name="fresh")
    return deals


async def test_the_overdue_filter_returns_only_overdue_rows_with_a_matching_total(
    env: DealEnv,
) -> None:
    deals = await _five_deals(env)

    page = await env.list.execute(DealQuery(overdue=True))

    assert _codes(page) == {_code(deals["both"]), _code(deals["overdue_only"])}
    assert page.total == 2
    assert {v.risk for v in page.items} <= {Risk.OVERDUE, Risk.OVERDUE_STALE}


async def test_the_stale_filter_returns_only_stale_rows_with_a_matching_total(
    env: DealEnv,
) -> None:
    deals = await _five_deals(env)

    page = await env.list.execute(DealQuery(stale=True))

    assert _codes(page) == {_code(deals["stale_only"]), _code(deals["both"])}
    assert page.total == 2
    assert {v.risk for v in page.items} <= {Risk.STALE, Risk.OVERDUE_STALE}


async def test_both_filters_together_return_a_deal_matching_either(env: DealEnv) -> None:
    deals = await _five_deals(env)

    page = await env.list.execute(DealQuery(overdue=True, stale=True))

    assert _codes(page) == {
        _code(deals["stale_only"]),
        _code(deals["both"]),
        _code(deals["overdue_only"]),
    }
    assert page.total == 3


async def test_without_the_filters_every_deal_is_listed(env: DealEnv) -> None:
    deals = await _five_deals(env)

    page = await env.list.execute(DealQuery())

    assert _codes(page) == {_code(v) for v in deals.values()}


async def test_a_risk_filter_combines_with_other_conditions_using_and(env: DealEnv) -> None:
    deals = await _five_deals(env)

    page = await env.list.execute(DealQuery(stale=True, keyword="both"))

    assert _codes(page) == {_code(deals["both"])}
    assert page.total == 1
