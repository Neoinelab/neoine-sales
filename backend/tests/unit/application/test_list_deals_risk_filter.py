"""ListDeals의 기한초과·미업데이트 필터(T-7~T-9).

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
            now=env.clock.now(),
            actor_user_id=ACTOR_ID,
            due_date=due_date,
        )
    )


def _codes(page: DealPage) -> set[str]:
    return {view.item.deal.id.value for view in page.items}


def _code(view: DealView) -> str:
    return view.item.deal.id.value


async def test_list_uses_the_business_today_and_the_saved_stale_days(env: DealEnv) -> None:
    """필터는 요청 시각의 업무 날짜와 저장된 경고 기준을 쓴다.

    테스트 코드: RK-030
    """
    # given: 경고 기준이 7일로 저장되어 있고 Deal이 7일 지났다
    await _save_threshold(env, 7)
    old = await env.new_deal()
    env.clock.advance(7 * DAY)  # 오늘 = 01-08, 마지막 갱신 01-01 -> 7일 경과

    # when: stale 필터로 조회한다
    page = await env.list.execute(DealQuery(stale=True))

    # then: 그 Deal만 나오고 risk가 stale이다
    assert _codes(page) == {_code(old)}
    assert page.items[0].risk is Risk.STALE


async def test_list_does_not_flag_a_deal_one_day_short_of_the_saved_stale_days(
    env: DealEnv,
) -> None:
    """저장된 기준에 하루 모자라면 stale 필터에 걸리지 않는다.

    테스트 코드: RK-030
    """
    # given: 경고 기준이 7일로 저장되어 있고 Deal이 6일 지났다
    await _save_threshold(env, 7)
    await env.new_deal()
    env.clock.advance(6 * DAY)

    # when: stale 필터로 조회한다
    page = await env.list.execute(DealQuery(stale=True))

    # then: 결과가 비어 있다
    assert (page.items, page.total) == ([], 0)


async def test_list_uses_the_default_stale_days_when_nothing_is_saved(env: DealEnv) -> None:
    """저장된 기준이 없으면 14일 기준으로 stale을 고른다.

    테스트 코드: RK-030
    """
    # given: 경고 기준을 저장한 적이 없고 Deal이 13일 지났다
    old = await env.new_deal()
    env.clock.advance(13 * DAY)
    assert (await env.list.execute(DealQuery(stale=True))).total == 0

    # when: 하루 더 지난 뒤 stale 필터로 조회한다
    env.clock.advance(DAY)  # 14일 경과

    page = await env.list.execute(DealQuery(stale=True))
    # then: 14일째에 그 Deal이 나온다
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
    """overdue 필터는 기한초과 Deal만 고르고 종결 Deal은 빠진다.

    테스트 코드: RK-027
    """
    # given: 기한초과만·미업데이트만·둘 다·정상·기한 지난 Lost Deal이 있다
    deals = await _five_deals(env)

    # when: overdue 필터로 조회한다
    page = await env.list.execute(DealQuery(overdue=True))

    # then: 기한초과만·둘 다 Deal만 나오고 total이 2이며 모든 행의 risk가 overdue 계열이다
    assert _codes(page) == {_code(deals["both"]), _code(deals["overdue_only"])}
    assert page.total == 2
    assert {v.risk for v in page.items} <= {Risk.OVERDUE, Risk.OVERDUE_STALE}


async def test_the_stale_filter_returns_only_stale_rows_with_a_matching_total(
    env: DealEnv,
) -> None:
    """stale 필터는 미업데이트 Deal만 고른다.

    테스트 코드: RK-028
    """
    # given: 기한초과만·미업데이트만·둘 다·정상·기한 지난 Lost Deal이 있다
    deals = await _five_deals(env)

    # when: stale 필터로 조회한다
    page = await env.list.execute(DealQuery(stale=True))

    # then: 미업데이트만·둘 다 Deal만 나오고 total이 2이며 모든 행의 risk가 stale 계열이다
    assert _codes(page) == {_code(deals["stale_only"]), _code(deals["both"])}
    assert page.total == 2
    assert {v.risk for v in page.items} <= {Risk.STALE, Risk.OVERDUE_STALE}


async def test_both_filters_together_return_a_deal_matching_either(env: DealEnv) -> None:
    """두 필터를 함께 켜면 어느 하나라도 해당하는 Deal이 나온다.

    테스트 코드: RK-029
    """
    # given: 기한초과만·미업데이트만·둘 다·정상·기한 지난 Lost Deal이 있다
    deals = await _five_deals(env)

    # when: overdue와 stale을 함께 켜고 조회한다
    page = await env.list.execute(DealQuery(overdue=True, stale=True))

    # then: 세 Deal이 나오고 total이 3이다
    assert _codes(page) == {
        _code(deals["stale_only"]),
        _code(deals["both"]),
        _code(deals["overdue_only"]),
    }
    assert page.total == 3


async def test_without_the_filters_every_deal_is_listed(env: DealEnv) -> None:
    """필터를 켜지 않으면 모든 Deal이 나온다.

    테스트 코드: RK-029
    """
    # given: 기한초과만·미업데이트만·둘 다·정상·기한 지난 Lost Deal이 있다
    deals = await _five_deals(env)

    # when: 필터 없이 조회한다
    page = await env.list.execute(DealQuery())

    # then: 다섯 Deal이 모두 나온다
    assert _codes(page) == {_code(v) for v in deals.values()}


async def test_a_risk_filter_combines_with_other_conditions_using_and(env: DealEnv) -> None:
    """경고 필터는 다른 조건과 AND로 결합한다."""
    # given: 기한초과만·미업데이트만·둘 다·정상·기한 지난 Lost Deal이 있다
    deals = await _five_deals(env)

    # when: stale 필터와 키워드 both로 조회한다
    page = await env.list.execute(DealQuery(stale=True, keyword="both"))

    # then: 둘 다 Deal 하나만 나온다
    assert _codes(page) == {_code(deals["both"])}
    assert page.total == 1
