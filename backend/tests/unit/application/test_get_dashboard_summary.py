"""GetDashboardSummary (Dashboard): 한 UoW에서 Forecast 타일·Status·분기·주의 타일을 모은다.

규칙 자체(Lost 제외·합계)는 도메인 테스트가, 저장소 묶음은 저장소 계약이 검증한다. 여기서는
Fake UoW 위의 결과(상태)로, 각 숫자가 어느 조건으로 만들어지는지(기간 적용/무시, Open만,
업무 날짜 기준)를 본다. 오늘은 2026-10-23(Seoul)이다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.dashboard.criteria import DashboardCriteria
from app.application.forecast.get_summary import GetForecastSummary
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.summary import Tally
from tests.factories import make_deal_action
from tests.support.user_ids import ACTOR_ID
from tests.unit.application.dashboard_summary_support import (
    DAY,
    add_verbal_code,
    criteria_of,
    go_to,
    new_deal,
    new_owner,
    save_threshold,
    seoul_noon_clock,
    summary,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from tests.fakes.unit_of_work import FixedClock
    from tests.unit.application.deal_env import DealEnv


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.fixture
def clock() -> FixedClock:
    return seoul_noon_clock()


def _statuses(view: Any) -> dict[str, Tally]:  # noqa: ANN401
    return {item.key: item.tally for item in view.statuses}


# ---- 요약 시각과 기간 (DSH-004~006) ----


async def test_summary_as_of_and_today_come_from_clock(env: DealEnv) -> None:
    """응답의 기준 시각과 업무 날짜는 서버 시계에서 온다.

    테스트 코드: DSH-004
    """
    # given: 서버 시계가 2026-10-23 12:00(Seoul)이다 (전제: clock fixture)
    # when: 2026년 Q4 요약을 조회한다
    view = await summary(env, criteria_of(quarters={4}))

    # then: as_of는 시계의 시각, today는 업무 날짜다
    assert view.as_of == env.clock.now()
    assert view.today == date(2026, 10, 23)


async def test_summary_echoes_the_period(env: DealEnv) -> None:
    """요약은 조회한 연도와 분기를 기간으로 그대로 돌려준다.

    테스트 코드: DSH-005
    """
    # when: 2026년 Q3 요약을 조회한다
    view = await summary(env, criteria_of(quarters={3}))

    # then: 기간은 2026년 Q3다
    assert view.period == ForecastPeriod(year=2026, quarters=frozenset({3}))


async def test_the_summary_period_keeps_the_chosen_quarters(env: DealEnv) -> None:
    """여러 분기를 고르면 기간이 고른 분기 집합을 그대로 가진다.

    테스트 코드: DSH-006
    """
    # given: Q1·Q3를 고른 조건
    period = ForecastPeriod(year=2026, quarters=frozenset({1, 3}))

    # when: 요약을 조회한다
    view = await summary(env, DashboardCriteria(period=period))

    # then: 기간이 Q1·Q3를 가진다
    assert view.period == period


# ---- Forecast 타일 (DSH-007~009) ----


async def test_summary_forecast_columns_include_an_added_open_code(env: DealEnv) -> None:
    """Forecast 열은 Lost를 뺀 코드 순서이고 추가한 Open 코드가 열과 Open 합계에 든다.

    테스트 코드: DSH-007
    """
    # given: admin이 Verbal 코드를 추가했고 2026년 Deal은 Verbal 70원·Pipeline 5원이다
    await add_verbal_code(env)
    await new_deal(env, "verbal", 70)
    await new_deal(env, "pipeline", 5)

    # when: 2026년 요약을 조회한다
    view = await summary(env)

    # then: 열과 셀은 같은 순서로 Verbal이 마지막이고 Lost는 없다
    keys = ["pipeline", "best", "most_likely", "commit", "won", "verbal"]
    assert [c.key for c in view.forecast_columns] == keys
    assert list(view.forecast_cells) == keys
    # then: Verbal 셀은 1건·70원, Open 합계는 2건·75원이다
    assert view.forecast_cells["verbal"] == Tally(1, 70)
    assert view.open_total == Tally(2, 75)


async def test_summary_forecast_part_equals_forecast_summary_total(env: DealEnv) -> None:
    """Dashboard Forecast 타일은 같은 연도·분기 조건의 Forecast 실시간 합계 행과 같다.

    테스트 코드: DSH-008
    """
    # given: 기본 담당자와 other의 Deal이 2026 Q1·Q4와 2027년에 있고 Lost도 있다
    other = await new_owner(env, "other")
    await new_deal(env, "pipeline", 100)
    await new_deal(env, "commit", 40, owner_user_id=other)
    await new_deal(env, "won", 500, date(2026, 12, 31))
    await new_deal(env, "lost", 999)
    await new_deal(env, "best", 7, date(2026, 2, 1))
    await new_deal(env, "best", 9, date(2027, 2, 1))
    criteria = DashboardCriteria(period=ForecastPeriod(year=2026, quarters=frozenset({4})))

    # when: Dashboard 요약과 같은 조건의 Forecast 실시간 요약을 조회한다
    view = await summary(env, criteria)
    expected = await GetForecastSummary(env.uow_factory, env.clock).execute(
        ForecastCriteria(period=ForecastPeriod(year=2026, quarters=frozenset({4})))
    )

    # then: 열·셀·Open 합계가 같고 Lost 열은 없다
    assert dict(view.forecast_cells) == dict(expected.total.cells)
    assert view.open_total == expected.total.open_total
    assert [c.key for c in view.forecast_columns] == [c.key for c in expected.columns]
    assert "lost" not in [c.key for c in view.forecast_columns]


@pytest.mark.parametrize("by_owner", [False, True], ids=["all-owners", "owner"])
@pytest.mark.parametrize("by_vendor", [False, True], ids=["all-vendors", "vendor"])
async def test_summary_forecast_part_equals_forecast_summary_with_owner_and_vendor(
    env: DealEnv, by_owner: bool, by_vendor: bool
) -> None:
    """담당자·Vendor 조건을 함께 줘도 Forecast 타일이 같은 조건의 Forecast 합계 행과 같다.

    테스트 코드: DSH-008
    """
    # given: other·기본 담당자의 Deal이 Vendor SAP·없음으로 섞여 있다
    other = await new_owner(env, "other")
    sap = await env.new_vendor("SAP")
    await new_deal(env, "pipeline", 1, owner_user_id=other, vendor_id=sap.id)
    await new_deal(env, "commit", 2, owner_user_id=other)
    await new_deal(env, "best", 4, vendor_id=sap.id)
    await new_deal(env, "won", 8, date(2026, 12, 31), owner_user_id=other, vendor_id=sap.id)
    await new_deal(env, "lost", 99, owner_user_id=other, vendor_id=sap.id)
    owner = other if by_owner else None
    vendor = sap.id if by_vendor else None

    # when: 같은 조건으로 Dashboard 요약과 Forecast 실시간 요약을 조회한다
    view = await summary(env, criteria_of(owner=owner, vendor=vendor))
    expected = await GetForecastSummary(env.uow_factory, env.clock).execute(
        ForecastCriteria(period=ForecastPeriod(year=2026), owner_user_id=owner, vendor_id=vendor)
    )

    # then: 열·셀·Open 합계가 같다
    assert [c.key for c in view.forecast_columns] == [c.key for c in expected.columns]
    assert dict(view.forecast_cells) == dict(expected.total.cells)
    assert view.open_total == expected.total.open_total


async def test_chosen_quarters_limit_tiles_and_status_but_not_the_quarter_rows(
    env: DealEnv,
) -> None:
    """Q1·Q3를 고르면 타일과 Status는 두 분기 Deal만 세고 분기 행은 그대로 네 개다.

    테스트 코드: DSH-009
    """
    # given: 2026-02-01 Pipeline 1원, 05-01 Commit 2원, 08-01 Best 4원, 2025-08-01 Pipeline 8원
    await new_deal(env, "pipeline", 1, date(2026, 2, 1))
    await new_deal(env, "commit", 2, date(2026, 5, 1))
    await new_deal(env, "best", 4, date(2026, 8, 1))
    await new_deal(env, "pipeline", 8, date(2025, 8, 1))

    # when: Q1·Q3를 골라 조회한다
    view = await summary(env, criteria_of(quarters={1, 3}))

    # then: Status 합계와 Open 합계는 2건·5원이고 Commit 셀은 0, Pipeline 셀은 1건·1원이다
    assert view.status_total == Tally(2, 1 + 4)
    assert view.open_total == Tally(2, 1 + 4)
    assert view.forecast_cells["pipeline"] == Tally(1, 1)
    assert view.forecast_cells["best"] == Tally(1, 4)
    assert view.forecast_cells["commit"] == Tally.ZERO
    # then: 분기 행은 Q1~Q4 네 개이고 고르지 않은 Q2 행에도 값이 있다
    assert [row.quarter for row in view.quarters] == [1, 2, 3, 4]
    assert view.quarters[1].total == Tally(1, 2)


async def test_forecast_tiles_equal_the_sum_of_the_chosen_quarter_rows(env: DealEnv) -> None:
    """고른 분기의 Forecast 타일 값은 그 분기 행 셀의 합과 같다.

    BDD 밖: DSH-009의 타일과 분기 행 일관성을 따로 확인한다.
    """
    # given: 분기마다 Pipeline Deal이 하나씩 있다
    await new_deal(env, "pipeline", 1, date(2026, 2, 1))
    await new_deal(env, "pipeline", 2, date(2026, 5, 1))
    await new_deal(env, "pipeline", 4, date(2026, 8, 1))
    await new_deal(env, "pipeline", 8, date(2026, 11, 1))

    # when: Q1·Q3를 골라 조회한다
    view = await summary(env, criteria_of(quarters={1, 3}))

    # then: Pipeline 타일은 Q1 행과 Q3 행 셀의 합이다
    rows = {row.quarter: row for row in view.quarters}
    assert view.forecast_cells["pipeline"] == Tally(
        rows[1].cells["pipeline"].count + rows[3].cells["pipeline"].count,
        rows[1].cells["pipeline"].amount + rows[3].cells["pipeline"].amount,
    )


# ---- Status (DSH-010~013) ----


async def test_summary_lists_every_status_in_code_order_with_zero_for_empty(env: DealEnv) -> None:
    """Status 항목은 모든 Status 코드를 순서대로 담고 Deal이 없으면 0이다.

    테스트 코드: DSH-010
    """
    # given: 기본 Status 코드 7개와 Deal 없음 (전제: env 시드)
    # when: 2026년 요약을 조회한다
    view = await summary(env)

    # then: 항목 key가 코드 순서이고 첫 이름은 기회발굴이며 모두 0이다
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
    """Status는 Lost를 빼고 Won을 넣으며 합계는 항목의 합이다.

    테스트 코드: DSH-011
    """
    # given: 기회발굴·Pipeline 100, POC완료·Commit 200, 계약완료·Won 300, 가격협상·Lost 400
    await new_deal(env, "pipeline", 100)
    await new_deal(env, "commit", 200, status_key="poc_completed")
    await new_deal(env, "won", 300)
    await new_deal(env, "lost", 400, status_key="price_negotiation")

    # when: 2026년 요약을 조회한다
    view = await summary(env)

    # then: Lost인 가격협상은 0이고 나머지는 각 1건이다
    tallies = _statuses(view)
    assert tallies["prospecting"] == Tally(1, 100)
    assert tallies["poc_completed"] == Tally(1, 200)
    assert tallies["contract_completed"] == Tally(1, 300)
    assert tallies["price_negotiation"] == Tally.ZERO
    # then: 합계는 3건·600원이다
    assert view.status_total == Tally(3, 600)


async def test_status_total_is_the_sum_of_items(env: DealEnv) -> None:
    """Status 합계는 항목 합계와 같다.

    테스트 코드: DSH-011
    """
    # given: 기회발굴 Deal 10원, 소개 Deal 20원
    await new_deal(env, "pipeline", 10)
    await new_deal(env, "best", 20, status_key="introduction")

    # when: 2026년 요약을 조회한다
    view = await summary(env)

    # then: 합계는 항목을 더한 2건·30원이다
    total = Tally.ZERO
    for item in view.statuses:
        total = total.add(item.tally)
    assert view.status_total == total == Tally(2, 30)


async def test_status_follows_year_quarter_owner_and_vendor(env: DealEnv) -> None:
    """Status는 연도·분기·담당자·Vendor 조건을 따르고 기간 밖 Deal은 빠진다.

    테스트 코드: DSH-012
    """
    # given: 기본 담당자의 Deal 4건(올해 Q1·Q4, 작년, 내년), other의 Q1 Deal, SAP인 Q1 Deal
    other = await new_owner(env, "other")
    sap = await env.new_vendor("SAP")
    await new_deal(env, "pipeline", 1, date(2026, 2, 1))
    await new_deal(env, "pipeline", 2, date(2026, 11, 1))
    await new_deal(env, "pipeline", 4, date(2025, 12, 31))
    await new_deal(env, "pipeline", 8, date(2027, 1, 1))
    await new_deal(env, "pipeline", 16, date(2026, 2, 2), owner_user_id=other)
    await new_deal(env, "pipeline", 32, date(2026, 2, 3), vendor_id=sap.id)

    # when: 연도만, Q1, 담당자 other, Vendor SAP 조건으로 각각 조회한다
    year = await summary(env)
    q1 = await summary(env, criteria_of(quarters={1}))
    by_owner = await summary(env, criteria_of(owner=other))
    by_vendor = await summary(env, criteria_of(vendor=sap.id))

    # then: 연도 안 4건, Q1 3건, other 1건, SAP 1건이고 작년·내년 Deal은 어디에도 없다
    assert year.status_total == Tally(4, 1 + 2 + 16 + 32)
    assert q1.status_total == Tally(3, 1 + 16 + 32)
    assert by_owner.status_total == Tally(1, 16)
    assert by_vendor.status_total == Tally(1, 32)


@pytest.mark.parametrize(
    ("deal_day", "year", "quarters", "expected_count"),
    [
        (date(2026, 12, 31), 2026, None, 1),
        (date(2026, 12, 31), 2026, {4}, 1),
        (date(2027, 1, 1), 2026, None, 0),
        (date(2027, 1, 1), 2027, {1}, 1),
        (date(2026, 3, 31), 2026, {1}, 1),
        (date(2026, 4, 1), 2026, {1}, 0),
    ],
    ids=["dec31-year", "dec31-q4", "jan1-prev-year", "jan1-next-q1", "mar31-q1", "apr1-not-q1"],
)
async def test_period_boundaries_include_both_ends_of_expected_close(
    env: DealEnv, deal_day: date, year: int, quarters: set[int] | None, expected_count: int
) -> None:
    """기간 경계는 Expected Close 양끝 포함이다(12-31·01-01·03-31·04-01).

    테스트 코드: DSH-013
    """
    # given: Expected Close가 경계일인 Deal 하나
    await new_deal(env, "pipeline", 1, deal_day)

    # when: 경계가 걸리는 연도·분기로 조회한다
    view = await summary(env, criteria_of(year=year, quarters=quarters))

    # then: Status 합계 건수가 기대와 같다
    assert view.status_total.count == expected_count


async def test_quarter_boundaries_put_dec_31_in_q4_and_jan_1_in_next_year(env: DealEnv) -> None:
    """분기 행에서도 12-31은 그 해 Q4, 01-01은 다음 해 Q1에 든다.

    테스트 코드: DSH-013
    """
    # given: Expected Close가 2026-12-31, 2027-01-01인 Deal
    await new_deal(env, "pipeline", 1, date(2026, 12, 31))
    await new_deal(env, "pipeline", 2, date(2027, 1, 1))

    # when: 2026년과 2027년 요약을 조회한다
    y2026 = await summary(env)
    y2027 = await summary(env, criteria_of(year=2027))

    # then: 12-31은 2026 Q4에, 01-01은 2027 Q1에 있고 2027 Q4는 비어 있다
    assert y2026.quarters[3].total == Tally(1, 1)
    assert y2027.quarters[0].total == Tally(1, 2)
    assert y2027.quarters[3].total == Tally.ZERO


# ---- 분기 행 (DSH-014~015) ----


async def test_quarters_cover_the_whole_year_even_with_a_quarter_filter(env: DealEnv) -> None:
    """분기 행은 고른 분기와 무관하게 Q1~Q4이고 합계는 Open + Won이며 Lost는 없다.

    테스트 코드: DSH-014
    """
    # given: 분기마다 Pipeline 1·Commit 2·Best 4·Won 8과 Lost 99
    await new_deal(env, "pipeline", 1, date(2026, 2, 1))
    await new_deal(env, "commit", 2, date(2026, 5, 1))
    await new_deal(env, "best", 4, date(2026, 8, 1))
    await new_deal(env, "won", 8, date(2026, 12, 31))
    await new_deal(env, "lost", 99, date(2026, 12, 30))

    # when: Q2를 골라 조회한다
    view = await summary(env, criteria_of(quarters={2}))

    # then: 분기 행은 고른 분기와 무관하게 Q1~Q4 네 개다
    assert [row.quarter for row in view.quarters] == [1, 2, 3, 4]
    # then: 합계는 1·2·4·8이고 Lost 99는 어디에도 없으며 Q4 Open 합계는 0(Won 제외)이다
    assert [row.total for row in view.quarters] == [
        Tally(1, 1),
        Tally(1, 2),
        Tally(1, 4),
        Tally(1, 8),
    ]
    assert view.quarters[3].open_total == Tally.ZERO
    # then: 상단 Status는 선택한 Q2만 센다
    assert view.status_total == Tally(1, 2)


async def test_quarters_match_the_forecast_summary_of_each_quarter(env: DealEnv) -> None:
    """분기 행은 담당자·Vendor 조건을 따르고 각 분기가 그 분기 Forecast 합계 행과 같다.

    테스트 코드: DSH-015
    """
    # given: 기본 담당자의 분기 경계 Deal 5건, other·SAP의 Q2 Deal, other의 Q2 Deal(Vendor 없음)
    other = await new_owner(env, "other")
    sap = await env.new_vendor("SAP")
    for number, day in enumerate(
        [
            date(2026, 1, 1),
            date(2026, 3, 31),
            date(2026, 4, 1),
            date(2026, 9, 30),
            date(2026, 10, 1),
        ]
    ):
        await new_deal(env, "commit" if number % 2 else "won", 10 + number, day)
    await new_deal(env, "pipeline", 5, date(2026, 6, 30), owner_user_id=other, vendor_id=sap.id)
    await new_deal(env, "best", 6, date(2026, 6, 30), owner_user_id=other)
    use_case = GetForecastSummary(env.uow_factory, env.clock)

    # when: other·SAP 조건으로 조회하고 분기마다 같은 조건의 Forecast 실시간 요약을 조회한다
    view = await summary(env, criteria_of(owner=other, vendor=sap.id))

    # then: 각 분기 행의 셀·Open 합계가 그 분기 Forecast 합계 행과 같고 합계는 Open + Won이다
    for row in view.quarters:
        expected = await use_case.execute(
            ForecastCriteria(
                period=ForecastPeriod(year=2026, quarters=frozenset({row.quarter})),
                owner_user_id=other,
                vendor_id=sap.id,
            )
        )
        assert dict(row.cells) == dict(expected.total.cells)
        assert row.open_total == expected.total.open_total
        assert row.total == row.open_total.add(row.cells["won"])
    # then: 다른 담당자·Vendor의 Deal은 들지 않는다(Q2에 SAP인 other의 Pipeline 5원만 있다)
    assert view.quarters[1].total == Tally(1, 5)
    assert sum(row.total.count for row in view.quarters) == 1


# ---- 주의 타일 (DSH-016~020) ----


async def test_overdue_count_ignores_period_and_excludes_closed_deals(env: DealEnv) -> None:
    """기한초과 수는 기간을 무시하고 종결 Deal·Due 오늘은 세지 않는다.

    테스트 코드: DSH-016
    """
    # given: 기간 밖(2024) Pipeline Deal(Due 어제)·Lost Deal(Due 어제), 2026-10-05 Deal(Due 오늘)
    old = await new_deal(env, "pipeline", 1, date(2024, 5, 1))
    closed = await new_deal(env, "lost", 1, date(2024, 5, 1))
    fresh = await new_deal(env, "pipeline", 1, date(2026, 10, 5))
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

    # when: 2026년 Q1 조건으로 조회한다
    attention = (await summary(env, criteria_of(quarters={1}))).attention

    # then: 기한초과는 old 1건뿐이다(기간 밖이어도 세고 Lost·Due 오늘은 제외)
    assert attention.overdue == 1


async def test_stale_count_ignores_period_and_follows_owner(env: DealEnv) -> None:
    """미업데이트 수는 기간을 무시하고 담당자 조건만 따른다.

    테스트 코드: DSH-016
    """
    # given: 경고 기준 7일, 2024년 Deal이 기본 담당자·other에 하나씩 있고 7일이 지났다
    other = await new_owner(env, "other")
    await save_threshold(env, 7)
    await new_deal(env, "pipeline", 1, date(2024, 5, 1))
    await new_deal(env, "pipeline", 1, date(2024, 5, 1), owner_user_id=other)
    env.clock.advance(7 * DAY)

    # when: 담당자 조건 없이, 그리고 other로 조회한다
    everyone = (await summary(env)).attention
    only_other = (await summary(env, criteria_of(owner=other))).attention

    # then: 전체는 2건, other는 1건이다
    assert everyone.stale == 2
    assert only_other.stale == 1


async def test_attention_counts_equal_the_deal_list_with_the_same_owner(env: DealEnv) -> None:
    """기한초과·미업데이트 수는 같은 담당자·Vendor의 Deal 목록 overdue·stale 건수와 같다.

    테스트 코드: DSH-016
    """
    # given: 경고 기준 7일, other의 기한초과 Deal과 7일 지난 Deal, 기본 담당자의 Deal
    from app.application.ports.deal_repository import DealQuery  # noqa: PLC0415
    from app.domain.deal.risk import RiskBasis  # noqa: PLC0415

    other = await new_owner(env, "other")
    await save_threshold(env, 7)
    late = await new_deal(env, "pipeline", 1, date(2024, 5, 1), owner_user_id=other)
    await new_deal(env, "pipeline", 1, date(2024, 5, 1))
    await env.uow.deal_actions.add(
        make_deal_action(
            deal_code=late.item.deal.id,
            acted_at=env.clock.now(),
            actor_user_id=ACTOR_ID,
            due_date=date(2026, 10, 22),
        )
    )
    env.clock.advance(7 * DAY)

    # when: other 조건으로 조회하고 같은 조건의 Deal 목록 건수를 센다
    attention = (await summary(env, criteria_of(owner=other))).attention
    basis = RiskBasis(today=date(2026, 10, 30), stale_days=7)
    overdue = await env.uow.deals.count(
        DealQuery(owner_user_id=other, overdue=True, risk_basis=basis)
    )
    stale = await env.uow.deals.count(DealQuery(owner_user_id=other, stale=True, risk_basis=basis))

    # then: 요약의 기한초과·미업데이트 수가 목록 건수와 같다
    assert (attention.overdue, attention.stale) == (overdue, stale)
    assert (overdue, stale) == (1, 1)


async def test_summary_uses_stored_stale_days_or_default_14(env: DealEnv) -> None:
    """미업데이트 기준일은 저장한 경고 기준이고 저장한 적이 없으면 14일이다.

    테스트 코드: DSH-017
    """
    # given: 경고 기준을 저장한 적이 없다
    # when: 조회한다
    before = (await summary(env)).attention.stale_days

    # then: 14일이다
    assert before == 14

    # given: 경고 기준을 30일로 저장한다
    await save_threshold(env, 30)
    # when: 다시 조회한다
    after = (await summary(env)).attention.stale_days

    # then: 30일이다
    assert after == 30


async def test_default_stale_days_14_marks_a_deal_exactly_on_the_fourteenth_day(
    env: DealEnv,
) -> None:
    """기본 기준에서는 등록 14일째부터 미업데이트다.

    테스트 코드: DSH-017
    """
    # given: 오늘 등록한 Deal 1건
    await new_deal(env)

    # when: 13일 뒤에 조회한다
    env.clock.advance(13 * DAY)
    day_13 = await summary(env)

    # then: 아직 미업데이트가 아니다
    assert day_13.attention.stale == 0

    # when: 하루 더 지난 14일 뒤에 조회한다
    env.clock.advance(DAY)
    day_14 = await summary(env)

    # then: 미업데이트 1건이다
    assert day_14.attention.stale == 1


async def test_closing_counts_are_open_deals_of_todays_month_and_quarter(env: DealEnv) -> None:
    """이번 달·이번 분기 Expected Close는 업무 날짜의 Open Deal만 센다.

    테스트 코드: DSH-018
    """
    # given: 10-05 Pipeline, 11-15 Commit, 10-30 Won, 10-10 Lost, 09-30·2027-01-01 Pipeline
    await new_deal(env, "pipeline", 1, date(2026, 10, 5))
    await new_deal(env, "commit", 1, date(2026, 11, 15))
    await new_deal(env, "won", 1, date(2026, 10, 30))
    await new_deal(env, "lost", 1, date(2026, 10, 10))
    await new_deal(env, "pipeline", 1, date(2026, 9, 30))
    await new_deal(env, "pipeline", 1, date(2027, 1, 1))

    # when: 2026년 요약을 조회한다
    attention = (await summary(env)).attention

    # then: 이번 달은 2026-10 1건, 이번 분기는 2026 Q4 2건이다
    assert (attention.closing_this_month.year, attention.closing_this_month.month) == (2026, 10)
    assert attention.closing_this_month.count == 1
    assert (attention.closing_this_quarter.year, attention.closing_this_quarter.quarter) == (
        2026,
        4,
    )
    assert attention.closing_this_quarter.count == 2


async def test_closing_counts_ignore_the_selected_period(env: DealEnv) -> None:
    """이번 달·이번 분기 수는 고른 기간을 무시한다.

    테스트 코드: DSH-018
    """
    # given: 2026-10-05 Pipeline Deal
    await new_deal(env, "pipeline", 1, date(2026, 10, 5))

    # when: 2020년 Q1로 조회한다
    attention = (await summary(env, criteria_of(year=2020, quarters={1}))).attention

    # then: 이번 달·이번 분기 수는 그대로 1건이다
    assert attention.closing_this_month.count == 1
    assert attention.closing_this_quarter.count == 1


async def test_attention_does_not_depend_on_the_chosen_quarters(env: DealEnv) -> None:
    """주의 타일은 고른 분기를 바꿔도 같다.

    테스트 코드: DSH-018
    """
    # given: 2026-10-05, 2026-02-05 Pipeline Deal
    await new_deal(env, "pipeline", 1, date(2026, 10, 5))
    await new_deal(env, "pipeline", 2, date(2026, 2, 5))

    # when: 분기 없이, Q1·Q2를 골라 조회한다
    plain = await summary(env)
    chosen = await summary(env, criteria_of(quarters={1, 2}))

    # then: 주의 타일이 같다
    assert chosen.attention == plain.attention


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
    """업무 날짜가 12-31이면 12월·Q4, 01-01이면 새해 1월·Q1이다.

    테스트 코드: DSH-019
    """
    # given: 서버 시계가 그날 정오다
    go_to(env, today)

    # when: 2026년 요약을 조회한다
    attention = (await summary(env)).attention

    # then: 이번 달·이번 분기의 연·월·분기가 업무 날짜 기준이다
    assert (attention.closing_this_month.year, attention.closing_this_month.month) == (year, month)
    assert (
        attention.closing_this_quarter.year,
        attention.closing_this_quarter.quarter,
    ) == (year, quarter)


async def test_deals_closing_on_new_year_boundary_count_in_their_own_quarter(env: DealEnv) -> None:
    """12-31과 01-01에 끝나는 Deal은 각각 그날의 이번 달·이번 분기에 센다.

    테스트 코드: DSH-019
    """
    # given: Expected Close 2026-12-31·2027-01-01인 Pipeline Deal
    await new_deal(env, "pipeline", 1, date(2026, 12, 31))
    await new_deal(env, "pipeline", 1, date(2027, 1, 1))

    # when: 오늘이 2026-12-31일 때와 2027-01-01일 때 조회한다
    go_to(env, date(2026, 12, 31))
    on_dec_31 = (await summary(env)).attention
    go_to(env, date(2027, 1, 1))
    on_jan_1 = (await summary(env)).attention

    # then: 12-31에는 12월·Q4 각 1건, 01-01에는 새해 1월·Q1 각 1건이다
    assert (on_dec_31.closing_this_month.count, on_dec_31.closing_this_quarter.count) == (1, 1)
    assert (on_jan_1.closing_this_month.count, on_jan_1.closing_this_quarter.count) == (1, 1)


async def test_closing_counts_follow_owner_and_vendor(env: DealEnv) -> None:
    """이번 달·이번 분기 Expected Close는 담당자·Vendor 조건을 따른다.

    테스트 코드: DSH-020
    """
    # given: 기본 담당자의 10-05 Deal, other의 10-06·11-06 Deal, Vendor SAP인 10-07 Deal
    other = await new_owner(env, "other")
    sap = await env.new_vendor("SAP")
    await new_deal(env, "pipeline", 1, date(2026, 10, 5))
    await new_deal(env, "pipeline", 1, date(2026, 10, 6), owner_user_id=other)
    await new_deal(env, "pipeline", 1, date(2026, 11, 6), owner_user_id=other)
    await new_deal(env, "pipeline", 1, date(2026, 10, 7), vendor_id=sap.id)

    # when: other로, SAP로 각각 조회한다
    by_owner = await summary(env, criteria_of(owner=other))
    by_vendor = await summary(env, criteria_of(vendor=sap.id))

    # then: other는 이번 달 1·이번 분기 2, SAP는 이번 분기 1이다
    assert by_owner.attention.closing_this_month.count == 1
    assert by_owner.attention.closing_this_quarter.count == 2
    assert by_vendor.attention.closing_this_quarter.count == 1


# ---- 빈 상태 (DSH-021) ----


async def test_summary_with_no_deals_is_all_zero(env: DealEnv) -> None:
    """Deal이 없으면 모든 숫자가 0이다.

    테스트 코드: DSH-021
    """
    # given: Deal 없음 (전제: env 시드)
    # when: 2026년 요약을 조회한다
    view = await summary(env)

    # then: Forecast 셀·Open 합계·Status·분기 행·주의 타일이 모두 0이다
    assert all(cell == Tally.ZERO for cell in view.forecast_cells.values())
    assert view.open_total == Tally.ZERO
    assert all(item.tally == Tally.ZERO for item in view.statuses)
    assert all(row.total == Tally.ZERO for row in view.quarters)
    attention = view.attention
    assert (attention.overdue, attention.stale) == (0, 0)
    assert (attention.closing_this_month.count, attention.closing_this_quarter.count) == (0, 0)


# ---- 금액 (DSH-024) ----


async def test_amounts_beyond_32_bits_are_summed_exactly(env: DealEnv) -> None:
    """금액은 원 합계 그대로이고 32비트를 넘어도 정확하다.

    테스트 코드: DSH-024
    """
    # given: 같은 Status의 2026년 Deal 두 건, 3,000,000,000원과 2,500,000,000원
    await new_deal(env, "pipeline", 3_000_000_000)
    await new_deal(env, "pipeline", 2_500_000_000)

    # when: 2026년 요약을 조회한다
    view = await summary(env)

    # then: 금액 합이 5,500,000,000원이다
    assert _statuses(view)["prospecting"] == Tally(2, 5_500_000_000)
    assert view.status_total == Tally(2, 5_500_000_000)
    assert view.forecast_cells["pipeline"] == Tally(2, 5_500_000_000)
