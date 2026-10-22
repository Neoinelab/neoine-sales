"""GetDashboardSummary (Dashboard AC-3~8): 한 UoW에서 Forecast 타일·Status·분기·주의 타일을 모은다.

규칙 자체(Lost 제외·합계)는 도메인 테스트가, 저장소 묶음은 저장소 계약이 검증한다. 여기서는
Fake UoW 위의
결과(상태)로, 각 숫자가 어느 조건으로 만들어지는지(기간 적용/무시, Open만, 업무 날짜 기준)를 본다.
오늘은 2026-10-23(Seoul)이다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pytest

from app.application.dashboard.criteria import DashboardCriteria
from app.application.dashboard.get_summary import GetDashboardSummary
from app.application.forecast.get_summary import GetForecastSummary
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.alert.thresholds import AlertThresholds
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.summary import Tally
from tests.factories import make_deal_action
from tests.factories_auth import make_user
from tests.fakes.unit_of_work import FixedClock
from tests.support.user_ids import ACTOR_ID, OWNER_ID, uid

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.deal.dto import DealView
    from app.domain.user.value_objects import UserId
    from tests.unit.application.deal_env import DealEnv

DAY = 24 * 3600
Y2026 = DashboardCriteria(period=ForecastPeriod(year=2026))


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 10, 23, 3, 0, tzinfo=UTC))  # Seoul 2026-10-23 12:00


def _status_for(forecast_key: str) -> str:
    return "contract_completed" if forecast_key == "won" else "prospecting"


async def _deal(
    env: DealEnv,
    forecast: str = "pipeline",
    amount: int = 100,
    day: date = date(2026, 10, 5),
    **overrides: Any,  # noqa: ANN401
) -> DealView:
    overrides.setdefault("status_key", _status_for(forecast))
    return await env.new_deal(
        forecast_key=forecast, revenue_amount=amount, revenue_date=day, **overrides
    )


async def _summary(env: DealEnv, criteria: DashboardCriteria = Y2026) -> Any:  # noqa: ANN401
    return await GetDashboardSummary(env.uow_factory, env.clock).execute(criteria)


def _statuses(view: Any) -> dict[str, Tally]:  # noqa: ANN401
    return {item.key: item.tally for item in view.statuses}


async def _owner(env: DealEnv, login: str) -> UserId:
    owner = uid(login)
    await env.uow.users.add(make_user(login, entity_id=owner))
    return owner


async def _save_threshold(env: DealEnv, days: int) -> None:
    async with env.uow_factory() as uow:
        await uow.alert_settings.save(
            AlertThresholds(stale_days=days), updated_by=OWNER_ID, now=env.clock.now()
        )
        await uow.commit()


def _go_to(env: DealEnv, day: date) -> None:
    """서버 시계를 그날 로컬 정오로 옮긴다."""
    target = datetime(day.year, day.month, day.day, 12).astimezone()
    env.clock.advance((target - env.clock.now()).total_seconds())


# ---- AC-4: Status ----


async def test_summary_lists_every_status_in_code_order_with_zero_for_empty(env: DealEnv) -> None:
    view = await _summary(env)

    assert [item.key for item in view.statuses] == [
        "prospecting",
        "introduction",
        "poc_preparation",
        "poc_completed",
        "technical_evaluation",
        "price_negotiation",
        "contract_completed",
    ]
    assert all(item.tally == Tally.ZERO for item in view.statuses)
    assert view.status_total == Tally.ZERO
    assert view.statuses[0].name == "기회발굴"
    assert [item.order for item in view.statuses] == sorted(i.order for i in view.statuses)


async def test_status_counts_exclude_lost_and_include_won(env: DealEnv) -> None:
    await _deal(env, "pipeline", 100)
    await _deal(env, "commit", 200, status_key="poc_completed")
    await _deal(env, "won", 300)
    await _deal(env, "lost", 400, status_key="price_negotiation")

    view = await _summary(env)

    tallies = _statuses(view)
    assert tallies["prospecting"] == Tally(1, 100)
    assert tallies["poc_completed"] == Tally(1, 200)
    assert tallies["contract_completed"] == Tally(1, 300)
    assert tallies["price_negotiation"] == Tally.ZERO
    assert view.status_total == Tally(3, 600)


async def test_status_total_is_the_sum_of_items(env: DealEnv) -> None:
    await _deal(env, "pipeline", 10)
    await _deal(env, "best", 20, status_key="introduction")

    view = await _summary(env)

    total = Tally.ZERO
    for item in view.statuses:
        total = total.add(item.tally)
    assert view.status_total == total == Tally(2, 30)


async def test_status_follows_year_quarter_owner_and_vendor(env: DealEnv) -> None:
    other = await _owner(env, "other")
    sap = await env.new_vendor("SAP")
    await _deal(env, "pipeline", 1, date(2026, 2, 1))  # Q1, 기본 담당자
    await _deal(env, "pipeline", 2, date(2026, 11, 1))  # Q4
    await _deal(env, "pipeline", 4, date(2025, 12, 31))  # 작년
    await _deal(env, "pipeline", 8, date(2027, 1, 1))  # 내년
    await _deal(env, "pipeline", 16, date(2026, 2, 2), owner_user_id=other)
    await _deal(env, "pipeline", 32, date(2026, 2, 3), vendor_id=sap.id)

    year = await _summary(env)
    q1 = await _summary(env, DashboardCriteria(period=ForecastPeriod(year=2026, quarter=1)))
    by_owner = await _summary(
        env, DashboardCriteria(period=ForecastPeriod(year=2026), owner_user_id=other)
    )
    by_vendor = await _summary(
        env, DashboardCriteria(period=ForecastPeriod(year=2026), vendor_id=sap.id)
    )

    assert year.status_total == Tally(4, 1 + 2 + 16 + 32)
    assert q1.status_total == Tally(3, 1 + 16 + 32)
    assert by_owner.status_total == Tally(1, 16)
    assert by_vendor.status_total == Tally(1, 32)


# ---- AC-3: Forecast 타일 ----


async def test_summary_forecast_part_equals_forecast_summary_total(env: DealEnv) -> None:
    other = await _owner(env, "other")
    await _deal(env, "pipeline", 100)
    await _deal(env, "commit", 40, owner_user_id=other)
    await _deal(env, "won", 500, date(2026, 12, 31))
    await _deal(env, "lost", 999)
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026, quarter=4))

    view = await _summary(env, criteria)
    expected = await GetForecastSummary(env.uow_factory, env.clock).execute(
        ForecastCriteria(period=ForecastPeriod(year=2026, quarter=4))
    )

    assert dict(view.forecast_cells) == dict(expected.total.cells)
    assert view.open_total == expected.total.open_total
    assert [c.key for c in view.forecast_columns] == [c.key for c in expected.columns]
    assert "lost" not in [c.key for c in view.forecast_columns]


async def test_summary_forecast_columns_include_an_added_open_code(env: DealEnv) -> None:
    from app.domain.code.entities import Code  # noqa: PLC0415
    from app.domain.code.values import CodeId, CodeKey, CodeKind  # noqa: PLC0415
    from tests.support.ids import new_id  # noqa: PLC0415

    await env.uow.codes.add(
        Code.create(
            entity_id=CodeId(new_id()),
            kind=CodeKind.FORECAST,
            name="Verbal",
            key=CodeKey("verbal"),
            order=99,
            probability_hint=None,
            now=env.clock.now(),
        )
    )
    await _deal(env, "verbal", 70)

    view = await _summary(env)

    assert [c.key for c in view.forecast_columns][-1] == "verbal"
    assert view.forecast_cells["verbal"] == Tally(1, 70)
    assert view.open_total == Tally(1, 70)


# ---- AC-5: 분기 ----


async def test_quarters_cover_the_whole_year_even_with_a_quarter_filter(env: DealEnv) -> None:
    await _deal(env, "pipeline", 1, date(2026, 2, 1))
    await _deal(env, "commit", 2, date(2026, 5, 1))
    await _deal(env, "best", 4, date(2026, 8, 1))
    await _deal(env, "won", 8, date(2026, 12, 31))
    await _deal(env, "lost", 99, date(2026, 12, 30))

    view = await _summary(env, DashboardCriteria(period=ForecastPeriod(year=2026, quarter=2)))

    assert [row.quarter for row in view.quarters] == [1, 2, 3, 4]
    assert [row.total for row in view.quarters] == [
        Tally(1, 1),
        Tally(1, 2),
        Tally(1, 4),
        Tally(1, 8),
    ]
    assert view.quarters[3].open_total == Tally.ZERO  # Won은 Open 합에서 빠진다
    assert view.status_total == Tally(1, 2)  # 상단 Status는 선택 분기만


async def test_quarters_match_the_forecast_summary_of_each_quarter(env: DealEnv) -> None:
    other = await _owner(env, "other")
    for number, day in enumerate(
        [
            date(2026, 1, 1),
            date(2026, 3, 31),
            date(2026, 4, 1),
            date(2026, 9, 30),
            date(2026, 10, 1),
        ]
    ):
        await _deal(env, "commit" if number % 2 else "won", 10 + number, day)
    await _deal(env, "pipeline", 5, date(2026, 6, 30), owner_user_id=other)
    use_case = GetForecastSummary(env.uow_factory, env.clock)

    view = await _summary(
        env, DashboardCriteria(period=ForecastPeriod(year=2026), owner_user_id=other)
    )

    for row in view.quarters:
        expected = await use_case.execute(
            ForecastCriteria(
                period=ForecastPeriod(year=2026, quarter=row.quarter), owner_user_id=other
            )
        )
        assert dict(row.cells) == dict(expected.total.cells)
        assert row.open_total == expected.total.open_total


async def test_quarter_boundaries_put_dec_31_in_q4_and_jan_1_in_next_year(env: DealEnv) -> None:
    await _deal(env, "pipeline", 1, date(2026, 12, 31))
    await _deal(env, "pipeline", 2, date(2027, 1, 1))

    y2026 = await _summary(env)
    y2027 = await _summary(env, DashboardCriteria(period=ForecastPeriod(year=2027)))

    assert y2026.quarters[3].total == Tally(1, 1)
    assert y2027.quarters[0].total == Tally(1, 2)
    assert y2027.quarters[3].total == Tally.ZERO


# ---- AC-6: 주의 타일 ----


async def test_closing_counts_are_open_deals_of_todays_month_and_quarter(env: DealEnv) -> None:
    await _deal(env, "pipeline", 1, date(2026, 10, 5))  # 이번 달, Open
    await _deal(env, "commit", 1, date(2026, 11, 15))  # 이번 분기, 이번 달 아님
    await _deal(env, "won", 1, date(2026, 10, 30))  # Won 제외
    await _deal(env, "lost", 1, date(2026, 10, 10))  # Lost 제외
    await _deal(env, "pipeline", 1, date(2026, 9, 30))  # 지난 분기
    await _deal(env, "pipeline", 1, date(2027, 1, 1))  # 다음 분기

    attention = (await _summary(env)).attention

    assert (attention.closing_this_month.year, attention.closing_this_month.month) == (2026, 10)
    assert attention.closing_this_month.count == 1
    assert (attention.closing_this_quarter.year, attention.closing_this_quarter.quarter) == (
        2026,
        4,
    )
    assert attention.closing_this_quarter.count == 2


async def test_closing_counts_ignore_the_selected_period(env: DealEnv) -> None:
    await _deal(env, "pipeline", 1, date(2026, 10, 5))

    attention = (
        await _summary(env, DashboardCriteria(period=ForecastPeriod(year=2020, quarter=1)))
    ).attention

    assert attention.closing_this_month.count == 1
    assert attention.closing_this_quarter.count == 1


async def test_closing_counts_follow_owner_and_vendor(env: DealEnv) -> None:
    other = await _owner(env, "other")
    sap = await env.new_vendor("SAP")
    await _deal(env, "pipeline", 1)
    await _deal(env, "pipeline", 1, owner_user_id=other)
    await _deal(env, "pipeline", 1, vendor_id=sap.id)

    by_owner = await _summary(
        env, DashboardCriteria(period=ForecastPeriod(year=2026), owner_user_id=other)
    )
    by_vendor = await _summary(
        env, DashboardCriteria(period=ForecastPeriod(year=2026), vendor_id=sap.id)
    )

    assert by_owner.attention.closing_this_month.count == 1
    assert by_vendor.attention.closing_this_quarter.count == 1


async def test_overdue_count_ignores_period_and_excludes_closed_deals(env: DealEnv) -> None:
    old = await _deal(env, "pipeline", 1, date(2024, 5, 1))
    closed = await _deal(env, "lost", 1, date(2024, 5, 1))
    fresh = await _deal(env, "pipeline", 1, date(2026, 10, 5))
    for view, due in (
        (old, date(2026, 10, 22)),
        (closed, date(2026, 10, 22)),
        (fresh, date(2026, 10, 23)),
    ):
        await env.uow.deal_actions.add(
            make_deal_action(
                deal_code=view.item.deal.id,
                acted_at=env.clock.now(),
                actor_user_id=ACTOR_ID,
                due_date=due,
            )
        )

    attention = (
        await _summary(env, DashboardCriteria(period=ForecastPeriod(year=2026, quarter=1)))
    ).attention

    assert (
        attention.overdue == 1
    )  # old만: 기간 밖이어도 세고, Lost는 빠지고, Due가 오늘이면 아직 아님


async def test_stale_count_ignores_period_and_follows_owner(env: DealEnv) -> None:
    other = await _owner(env, "other")
    await _save_threshold(env, 7)
    await _deal(env, "pipeline", 1, date(2024, 5, 1))
    await _deal(env, "pipeline", 1, date(2024, 5, 1), owner_user_id=other)
    env.clock.advance(7 * DAY)

    everyone = (await _summary(env)).attention
    only_other = (
        await _summary(
            env, DashboardCriteria(period=ForecastPeriod(year=2026), owner_user_id=other)
        )
    ).attention

    assert everyone.stale == 2
    assert only_other.stale == 1


async def test_summary_uses_stored_stale_days_or_default_14(env: DealEnv) -> None:
    assert (await _summary(env)).attention.stale_days == 14

    await _save_threshold(env, 30)

    assert (await _summary(env)).attention.stale_days == 30


async def test_default_stale_days_14_marks_a_deal_exactly_on_the_fourteenth_day(
    env: DealEnv,
) -> None:
    await _deal(env)
    env.clock.advance(13 * DAY)
    assert (await _summary(env)).attention.stale == 0

    env.clock.advance(DAY)

    assert (await _summary(env)).attention.stale == 1


# ---- AC-7: 업무 날짜 경계 ----


@pytest.mark.parametrize(
    ("today", "year", "quarter", "month"),
    [
        (date(2026, 12, 31), 2026, 4, 12),
        (date(2027, 1, 1), 2027, 1, 1),
    ],
)
async def test_this_month_and_quarter_switch_on_the_business_date(
    env: DealEnv, today: date, year: int, quarter: int, month: int
) -> None:
    _go_to(env, today)

    attention = (await _summary(env)).attention

    assert (attention.closing_this_month.year, attention.closing_this_month.month) == (year, month)
    assert (
        attention.closing_this_quarter.year,
        attention.closing_this_quarter.quarter,
    ) == (year, quarter)


async def test_deals_closing_on_new_year_boundary_count_in_their_own_quarter(env: DealEnv) -> None:
    await _deal(env, "pipeline", 1, date(2026, 12, 31))
    await _deal(env, "pipeline", 1, date(2027, 1, 1))
    _go_to(env, date(2026, 12, 31))
    on_dec_31 = (await _summary(env)).attention
    _go_to(env, date(2027, 1, 1))

    on_jan_1 = (await _summary(env)).attention

    assert on_dec_31.closing_this_quarter.count == 1
    assert on_jan_1.closing_this_quarter.count == 1
    assert on_jan_1.closing_this_month.count == 1


# ---- AC-8: 기준 시각 ----


async def test_summary_as_of_and_today_come_from_clock(env: DealEnv) -> None:
    view = await _summary(env)

    assert view.as_of == env.clock.now()
    assert view.today == date(2026, 10, 23)


async def test_summary_echoes_the_period(env: DealEnv) -> None:
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026, quarter=3))

    assert (await _summary(env, criteria)).period == ForecastPeriod(year=2026, quarter=3)


async def test_summary_with_no_deals_is_all_zero(env: DealEnv) -> None:
    view = await _summary(env)

    assert all(cell == Tally.ZERO for cell in view.forecast_cells.values())
    assert view.open_total == Tally.ZERO
    assert all(row.total == Tally.ZERO for row in view.quarters)
    attention = view.attention
    assert (attention.overdue, attention.stale) == (0, 0)
    assert (attention.closing_this_month.count, attention.closing_this_quarter.count) == (0, 0)
