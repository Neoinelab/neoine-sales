"""GetDashboardSummary와 Deal 목록 원장의 정합성 (Dashboard): 모든 숫자 = 같은 조건 Deal 목록.

각 숫자를 만든 조건(`DashboardCriteria`가 정의하는 Deal 목록 조건)으로 Fake Deal 저장소를 검색해
센 건수·금액과 요약의 숫자를 비교한다. 오늘은 Seoul 2026-10-23 12:00에서 2일 흐른 10-25다.
"""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.code.values import ForecastOutcome
from app.domain.deal.risk import RiskBasis
from tests.factories import make_deal_action
from tests.support.user_ids import ACTOR_ID
from tests.unit.application.dashboard_summary_support import (
    DAY,
    add_verbal_code,
    criteria_of,
    ledger,
    new_deal,
    new_owner,
    save_threshold,
    seoul_noon_clock,
    summary,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from app.domain.forecast.summary import Tally
    from app.domain.user.value_objects import UserId
    from app.domain.vendor.values import VendorId
    from tests.fakes.unit_of_work import FixedClock
    from tests.unit.application.deal_env import DealEnv


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.fixture
def clock() -> FixedClock:
    return seoul_noon_clock()


@dataclass
class Seed:
    kim: UserId
    lee: UserId
    sap: VendorId
    oracle: VendorId


def _cell(tally: Tally) -> tuple[int, int]:
    return tally.count, tally.amount


async def _given_ten_deals(env: DealEnv) -> Seed:
    """KIM·LEE, Vendor SAP·Oracle, 2025-12-31~2027-01-01에 걸친 여러 Status·Forecast의 Deal 10건."""
    kim = await new_owner(env, "kim")
    lee = await new_owner(env, "lee")
    sap = (await env.new_vendor("SAP")).id
    oracle = (await env.new_vendor("Oracle")).id
    rows = (
        (kim, None, "pipeline", 10, date(2026, 1, 1), sap),
        (kim, "introduction", "best", 20, date(2026, 3, 31), oracle),
        (kim, "poc_completed", "commit", 30, date(2026, 4, 1), sap),
        (lee, None, "most_likely", 40, date(2026, 10, 5), sap),
        (lee, "price_negotiation", "lost", 50, date(2026, 10, 10), sap),
        (lee, None, "won", 60, date(2026, 12, 31), oracle),
        (kim, None, "pipeline", 70, date(2026, 11, 15), sap),
        (kim, "technical_evaluation", "commit", 80, date(2026, 11, 30), oracle),
        (lee, None, "pipeline", 90, date(2025, 12, 31), sap),
        (lee, None, "pipeline", 100, date(2027, 1, 1), sap),
    )
    for owner, status, forecast, amount, day, vendor in rows:
        overrides = {"status_key": status} if status else {}
        await new_deal(
            env, forecast, amount, day, owner_user_id=owner, vendor_id=vendor, **overrides
        )
    return Seed(kim=kim, lee=lee, sap=sap, oracle=oracle)


async def _given_overdue_and_stale(env: DealEnv, seed: Seed) -> None:
    """2일이 지나 경고 기준 2일로 두고, 담당자 KIM의 Deal에만 어제가 Due인 Action을 남긴다."""
    await save_threshold(env, 2)
    env.clock.advance(2 * DAY)
    for item in await env.uow.deals.search(DealQuery(owner_user_id=seed.kim, limit=200)):
        await env.uow.deal_actions.add(
            make_deal_action(
                deal_code=item.deal.id,
                now=env.clock.now(),
                actor_user_id=ACTOR_ID,
                due_date=date(2026, 10, 24),
            )
        )


@dataclass
class World:
    """열 개 Deal을 둔 환경과 조건 조합(분기·담당자·Vendor)."""

    env: DealEnv
    seed: Seed
    quarters: set[int] | None
    owner: UserId | None
    vendor: VendorId | None

    @property
    def common(self) -> dict[str, Any]:
        return {"owner_user_id": self.owner, "vendor_id": self.vendor}

    @property
    def period(self) -> dict[str, Any]:
        return {"year": 2026, "quarters": frozenset(self.quarters) if self.quarters else None}

    async def summary(self) -> Any:  # noqa: ANN401
        return await summary(
            self.env, criteria_of(quarters=self.quarters, owner=self.owner, vendor=self.vendor)
        )

    async def ledger(self, **extra: Any) -> tuple[int, int]:  # noqa: ANN401
        return await ledger(self.env, DealQuery(**self.period, **self.common, **extra))


@pytest.fixture(
    params=[
        pytest.param((False, False, False), id="year"),
        pytest.param((True, False, False), id="year-quarter"),
        pytest.param((True, True, False), id="quarter-owner"),
        pytest.param((True, True, True), id="quarter-owner-vendor"),
        pytest.param((False, False, True), id="year-vendor"),
    ]
)
async def world(env: DealEnv, request: pytest.FixtureRequest) -> World:
    by_quarter, by_owner, by_vendor = request.param
    seed = await _given_ten_deals(env)
    await _given_overdue_and_stale(env, seed)
    return World(
        env=env,
        seed=seed,
        quarters={4} if by_quarter else None,
        owner=seed.kim if by_owner else None,
        vendor=seed.sap if by_vendor else None,
    )


async def test_forecast_tiles_and_open_total_match_the_ledger(world: World) -> None:
    """Forecast 셀과 Open 합계가 같은 조건 Deal 목록 원장과 같다.

    테스트 코드: DSH-022
    """
    # when: 조건으로 요약을 조회한다 (전제: world — 열 개 Deal과 조건 조합 5가지)
    view = await world.summary()

    # then: Forecast 셀이 forecast_key 목록 원장과 같다
    for key, tally in view.forecast_cells.items():
        assert await world.ledger(forecast_keys=frozenset({key})) == _cell(tally), key
    # then: Open 합계가 Open 목록 원장과 같다
    open_found = await world.ledger(forecast_outcome=ForecastOutcomeFilter.OPEN)
    assert open_found == _cell(view.open_total)


async def test_status_items_and_total_match_the_not_lost_ledger(world: World) -> None:
    """Status 항목과 합계가 Lost 제외 목록 원장과 같다.

    테스트 코드: DSH-022
    """
    # when: 조건으로 요약을 조회한다 (전제: world)
    view = await world.summary()

    # then: Status 항목이 status_key + Lost 제외 목록 원장과 같다
    for item in view.statuses:
        found = await world.ledger(
            status_key=item.key, forecast_outcome=ForecastOutcomeFilter.NOT_LOST
        )
        assert found == _cell(item.tally), item.key
    # then: 합계가 Lost 제외 목록 원장과 같다
    not_lost = await world.ledger(forecast_outcome=ForecastOutcomeFilter.NOT_LOST)
    assert not_lost == _cell(view.status_total)


async def test_attention_counts_match_the_ledger(world: World) -> None:
    """기한초과·미업데이트·이번 달·이번 분기가 같은 조건 목록 건수와 같다.

    테스트 코드: DSH-022
    """
    # when: 조건으로 요약을 조회한다 (전제: world)
    view = await world.summary()

    # then: 기한초과·미업데이트는 담당자·Vendor만 같은 목록 건수와 같고 0이 아니다
    attention = view.attention
    basis = RiskBasis(today=view.today, stale_days=attention.stale_days)
    overdue = await ledger(world.env, DealQuery(**world.common, overdue=True, risk_basis=basis))
    stale = await ledger(world.env, DealQuery(**world.common, stale=True, risk_basis=basis))
    assert (overdue[0], stale[0]) == (attention.overdue, attention.stale)
    assert (attention.overdue, attention.stale) != (0, 0)
    # then: 이번 달·이번 분기는 업무 날짜 기준 Open 목록 건수와 같다
    month, quarter = attention.closing_this_month, attention.closing_this_quarter
    month_found = await ledger(
        world.env,
        DealQuery(
            year=month.year,
            month=month.month,
            **world.common,
            forecast_outcome=ForecastOutcomeFilter.OPEN,
        ),
    )
    quarter_found = await ledger(
        world.env,
        DealQuery(
            year=quarter.year,
            quarters=frozenset({quarter.quarter}),
            **world.common,
            forecast_outcome=ForecastOutcomeFilter.OPEN,
        ),
    )
    assert month_found[0] == month.count
    assert quarter_found[0] == quarter.count


async def test_quarter_rows_match_the_ledger_of_each_quarter(world: World) -> None:
    """분기 행의 셀·Open 합계·합계가 그 분기 목록 원장과 같다(고른 분기와 무관).

    테스트 코드: DSH-022
    """
    # when: 조건으로 요약을 조회한다 (전제: world)
    view = await world.summary()

    # then: 각 분기 행이 연도·그 분기·담당자·Vendor 목록 원장과 같다
    for row in view.quarters:
        row_query = {"year": 2026, "quarters": frozenset({row.quarter}), **world.common}
        for key, tally in row.cells.items():
            found = await ledger(world.env, DealQuery(**row_query, forecast_keys=frozenset({key})))
            assert found == _cell(tally), (row.quarter, key)
        open_row = await ledger(
            world.env, DealQuery(**row_query, forecast_outcome=ForecastOutcomeFilter.OPEN)
        )
        total_row = await ledger(
            world.env, DealQuery(**row_query, forecast_outcome=ForecastOutcomeFilter.NOT_LOST)
        )
        assert open_row == _cell(row.open_total)
        assert total_row == _cell(row.total)


@pytest.mark.parametrize(
    ("quarters", "open_count", "not_lost_count"),
    [(None, 3, 4), ({1, 3}, 2, 2)],
    ids=["year", "q1-q3"],
)
async def test_open_and_not_lost_key_sets_match_the_deal_list_totals(
    env: DealEnv, quarters: set[int] | None, open_count: int, not_lost_count: int
) -> None:
    """Open 합계·Lost 제외 합계는 응답 Forecast 열로 만든 key 집합 목록 total과 같다.

    테스트 코드: DSH-023
    """
    # given: 추가 Open 코드 Verbal과 2026년 Deal: Pipeline 10, Commit 20, Verbal 30, Won 40, Lost 50
    await add_verbal_code(env)
    await new_deal(env, "pipeline", 10, date(2026, 2, 1))
    await new_deal(env, "commit", 20, date(2026, 5, 1))
    await new_deal(env, "verbal", 30, date(2026, 8, 1))
    await new_deal(env, "won", 40, date(2026, 11, 1))
    await new_deal(env, "lost", 50, date(2026, 2, 2))
    view = await summary(env, criteria_of(quarters=quarters))

    # when: 응답 Forecast 열에서 Open 집합·Lost 제외 집합을 만들어 같은 기간 목록을 조회한다
    open_keys = frozenset(c.key for c in view.forecast_columns if c.outcome is ForecastOutcome.OPEN)
    not_lost_keys = frozenset(
        c.key for c in view.forecast_columns if c.outcome is not ForecastOutcome.LOST
    )
    chosen = frozenset(quarters) if quarters else None
    open_total = await env.uow.deals.count(
        DealQuery(year=2026, quarters=chosen, forecast_keys=open_keys)
    )
    not_lost_total = await env.uow.deals.count(
        DealQuery(year=2026, quarters=chosen, forecast_keys=not_lost_keys)
    )

    # then: Open 집합에 Verbal이 있고 목록 total이 Open 합계·Status 합계 건수와 같다
    assert "verbal" in open_keys
    assert open_total == view.open_total.count == open_count
    assert not_lost_total == view.status_total.count == not_lost_count
