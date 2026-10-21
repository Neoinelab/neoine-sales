"""Forecast 스냅숏 유스케이스 단위 테스트의 공용 준비 도우미(P6 R2).

Deal 환경(`DealEnv`) 위에서 Deal·담당자를 만들고, 스냅숏 저장소에 셀을 직접 넣는다. 시각은 서버 OS
로컬 시간대의 달력 날짜로 해석되므로 로컬 시각으로 만든다(`local`).
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from app.domain.code.values import ForecastOutcome
from app.domain.forecast.snapshot import (
    ForecastSnapshot,
    SnapshotCell,
    SnapshotColumn,
    YearMonth,
)
from app.domain.forecast.summary import Tally
from tests.factories_auth import make_user
from tests.support.user_ids import OWNER_ID, uid

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.user.value_objects import UserId
    from tests.unit.application.deal_env import DealEnv

OUTCOMES = {"won": ForecastOutcome.WON, "lost": ForecastOutcome.LOST}
ORDERS = {"pipeline": 1, "best": 2, "most_likely": 3, "commit": 4, "won": 5, "lost": 6}
IN_Q3 = date(2026, 8, 15)


def local(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """서버 OS 로컬 시간대의 시각(업무 날짜가 이 달력 날짜가 된다)."""
    return datetime(year, month, day, hour, minute).astimezone()


async def new_deal(
    env: DealEnv,
    forecast: str = "pipeline",
    amount: int = 100,
    day: date = IN_Q3,
    **overrides: Any,  # noqa: ANN401
) -> None:
    await env.new_deal(
        forecast_key=forecast,
        status_key="contract_completed" if forecast == "won" else "prospecting",
        revenue_amount=amount,
        revenue_date=day,
        **overrides,
    )


async def new_owner(env: DealEnv, login: str) -> UserId:
    owner = uid(login)
    await env.uow.users.add(make_user(login, entity_id=owner))
    return owner


async def resign(env: DealEnv, owner: UserId) -> None:
    user = await env.uow.users.get(owner)
    user.resign(env.clock.now())
    await env.uow.users.update(user)


def column(key: str, name: str | None = None) -> SnapshotColumn:
    return SnapshotColumn(
        key=key,
        name=name or key.title(),
        outcome=OUTCOMES.get(key, ForecastOutcome.OPEN),
        order=ORDERS[key],
    )


DEFAULT_COLUMNS = tuple(column(key) for key in ORDERS)


def cell(  # noqa: PLR0913, PLR0917 - 셀의 독립 필드
    year: int,
    month: int,
    key: str = "pipeline",
    count: int = 1,
    amount: int = 100,
    owner: UserId = OWNER_ID,
) -> SnapshotCell:
    return SnapshotCell(
        revenue_year=year,
        revenue_month=month,
        owner_id=owner,
        forecast_key=key,
        tally=Tally(count, amount),
    )


async def store_snapshot(
    env: DealEnv,
    period: YearMonth,
    taken_at: datetime,
    *cells: SnapshotCell,
    columns: Sequence[SnapshotColumn] = DEFAULT_COLUMNS,
) -> None:
    """저장 당시의 코드 목록(기본: 기본 Forecast 6개)과 셀로 스냅숏을 저장소에 직접 넣는다."""
    await env.uow.forecast_snapshots.replace(
        ForecastSnapshot(period=period, taken_at=taken_at, columns=list(columns), cells=list(cells))
    )


def cell_keys(cells: Any) -> set[tuple[int, int, int, str, int, int]]:  # noqa: ANN401
    """셀을 (연, 월, 담당자, key, 건수, 금액) 집합으로 바꿔 순서와 무관하게 비교한다."""
    return {
        (c.revenue_year, c.revenue_month, c.owner_id, c.forecast_key, c.tally.count, c.tally.amount)
        for c in cells
    }
