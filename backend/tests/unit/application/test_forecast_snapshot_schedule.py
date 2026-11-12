"""EnsureMonthlyForecastSnapshot + TakeForecastSnapshot 조립: 자동 저장 결과를 읽기 쪽까지 본다.

작업 잠금만 Fake(`FakeJobLock`)이고 저장·요약·목록은 실제 유스케이스를 Fake UoW 위에서 돌린다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from app.application.forecast.ensure_monthly_snapshot import (
    EnsureMonthlyForecastSnapshot,
    SnapshotCheckOutcome,
)
from app.application.forecast.get_snapshot_summary import GetForecastSnapshotSummary
from app.application.forecast.list_snapshots import ListForecastSnapshots
from app.application.forecast.take_snapshot import TakeForecastSnapshot
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.snapshot import YearMonth
from app.domain.forecast.summary import Tally
from tests.fakes.job_lock import FakeJobLock
from tests.fakes.unit_of_work import FixedClock
from tests.unit.application.forecast_snapshot_env import given_kim_and_lee_deals, local, new_deal

if TYPE_CHECKING:
    from app.application.forecast.views import ForecastSummaryView
    from app.domain.user.value_objects import UserId
    from tests.unit.application.deal_env import DealEnv

SEPT = YearMonth(2026, 9)
RUN = local(2026, 10, 1, 0, 5)
LATER = local(2026, 10, 1, 9, 0)
MID = local(2026, 10, 15, 14, 30)
AUG = local(2026, 9, 1, 0, 5)
Q3 = ForecastPeriod(year=2026, quarters=frozenset({3}))
Q4 = ForecastPeriod(year=2026, quarters=frozenset({4}))


def _ensure(env: DealEnv, now: datetime) -> EnsureMonthlyForecastSnapshot:
    clock = FixedClock(now)
    return EnsureMonthlyForecastSnapshot(
        env.uow_factory, clock, FakeJobLock(), TakeForecastSnapshot(env.uow_factory, clock)
    )


async def _periods(env: DealEnv) -> list[tuple[str, datetime]]:
    infos = await ListForecastSnapshots(env.uow_factory).execute()
    return [(str(info.period), info.taken_at) for info in infos]


async def _september_summary(env: DealEnv, period: ForecastPeriod) -> ForecastSummaryView:
    return await GetForecastSnapshotSummary(env.uow_factory).execute(
        SEPT, ForecastCriteria(period=period)
    )


def _cells(view: ForecastSummaryView, owner: UserId) -> dict[str, Tally]:
    row = next(r for r in view.rows if r.owner and r.owner.id == owner)
    return {key: tally for key, tally in row.cells.items() if tally != Tally.ZERO}


async def test_missing_previous_month_is_taken_and_readable(env: DealEnv) -> None:
    """전월 스냅숏이 없으면 확인이 만들고 taken이며 요약에서 읽힌다.

    테스트 코드: FC-037
    """
    # given: KIM·LEE의 Deal이 있고 스냅숏은 없다
    kim, lee = await given_kim_and_lee_deals(env)
    # when: RUN 시각에 확인을 한 번 한다
    result = await _ensure(env, RUN).execute()
    # then: 결과는 taken이고 목록은 2026-09(생성 시각 RUN)다
    assert result.outcome is SnapshotCheckOutcome.TAKEN
    assert await _periods(env) == [("2026-09", RUN)]
    # then: 2026-09 요약 Q3의 KIM·LEE 행과 Q4의 KIM 행이 저장된 값이다
    q3 = await _september_summary(env, Q3)
    assert _cells(q3, kim) == {
        "pipeline": Tally(2, 140),
        "commit": Tally(1, 7),
        "won": Tally(1, 500),
    }
    assert next(r for r in q3.rows if r.owner and r.owner.id == kim).open_total == Tally(3, 147)
    assert _cells(q3, lee) == {"best": Tally(1, 30)}
    assert _cells(await _september_summary(env, Q4), kim) == {"pipeline": Tally(1, 5000)}


async def test_existing_previous_month_is_not_replaced_by_a_later_check(env: DealEnv) -> None:
    """전월 스냅숏이 있으면 확인은 아무것도 바꾸지 않고 already-exists다.

    테스트 코드: FC-038
    """
    # given: RUN 시각에 만든 2026-09 스냅숏, 그 뒤 KIM의 pipeline 1000(2026-08-10) 추가
    kim, _ = await given_kim_and_lee_deals(env)
    await _ensure(env, RUN).execute()
    await new_deal(env, "pipeline", 1000, date(2026, 8, 10), owner_user_id=kim)
    # when: LATER 시각에 확인한다
    result = await _ensure(env, LATER).execute()
    # then: already-exists이고 생성 시각·요약 값은 그대로다
    assert result.outcome is SnapshotCheckOutcome.ALREADY_EXISTS
    assert await _periods(env) == [("2026-09", RUN)]
    q3 = await _september_summary(env, Q3)
    assert _cells(q3, kim) == {
        "pipeline": Tally(2, 140),
        "commit": Tally(1, 7),
        "won": Tally(1, 500),
    }
    assert next(r for r in q3.rows if r.owner and r.owner.id == kim).open_total == Tally(3, 147)
    assert _cells(await _september_summary(env, Q4), kim) == {"pipeline": Tally(1, 5000)}


async def test_a_mid_month_first_check_takes_only_the_previous_month(env: DealEnv) -> None:
    """그달 중순 첫 확인이 전월분을 만들고 전전월 이전은 만들지 않는다.

    테스트 코드: FC-039
    """
    # given: Deal은 있으나 10월 초에 앱이 꺼져 있어 스냅숏이 없다
    await given_kim_and_lee_deals(env)
    # when: MID 시각에 확인한다
    result = await _ensure(env, MID).execute()
    # then: taken이고 목록은 2026-09뿐이며 생성 시각은 MID다
    assert result.outcome is SnapshotCheckOutcome.TAKEN
    assert await _periods(env) == [("2026-09", MID)]


async def test_checks_of_two_months_list_the_newest_period_first(env: DealEnv) -> None:
    """두 달의 확인이 쌓이면 목록은 최근 기준 월부터다.

    테스트 코드: FC-042
    """
    # given: AUG 시각에 확인으로 만든 2026-08 스냅숏
    await given_kim_and_lee_deals(env)
    await _ensure(env, AUG).execute()
    # when: RUN 시각에 확인한다
    result = await _ensure(env, RUN).execute()
    # then: taken이고 목록은 2026-09(RUN), 2026-08(AUG) 순이다
    assert result.outcome is SnapshotCheckOutcome.TAKEN
    assert await _periods(env) == [("2026-09", RUN), ("2026-08", AUG)]
