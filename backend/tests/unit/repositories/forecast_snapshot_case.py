"""ForecastSnapshotRepository 계약 테스트 공용 case (Fake와 SQL, P6 R2).

스냅숏 셀은 담당자(users)를 FK로 참조하므로 case는 사용자 저장소를 함께 가지고 `ensure_owner`로
참조 대상을 미리 만든다. Fake는 `FakeUnitOfWork`의 저장소, SQL은 한 세션 위의 Sql 저장소다
(구현 모듈은 사용 시점에 가져온다).
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.code.values import ForecastOutcome
from app.domain.forecast.summary import Tally
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.database import rolled_back_session
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.engine import URL

    from app.domain.forecast.snapshot import (
        ForecastSnapshot,
        SnapshotCell,
        SnapshotColumn,
        YearMonth,
    )
    from app.domain.user.value_objects import UserId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
TAKEN_AT = datetime(2026, 10, 1, 0, 5, tzinfo=UTC)
OUTCOMES = {"won": ForecastOutcome.WON, "lost": ForecastOutcome.LOST}
ORDERS = {"pipeline": 1, "best": 2, "most_likely": 3, "commit": 4, "won": 5, "lost": 6}


@dataclass
class SnapshotCase:
    snapshots: Any
    users: Any

    async def ensure_owner(self, user_id: UserId = OWNER_ID) -> UserId:
        await ensure_users(self.users, user_id)
        return user_id


def make_column(key: str, name: str | None = None) -> SnapshotColumn:
    from app.domain.forecast.snapshot import SnapshotColumn  # noqa: PLC0415 - 구현 지연 import

    return SnapshotColumn(
        key=key,
        name=name or key.title(),
        outcome=OUTCOMES.get(key, ForecastOutcome.OPEN),
        order=ORDERS[key],
    )


def default_columns() -> list[SnapshotColumn]:
    """기본 Forecast 코드 6개(셀의 key는 같은 스냅숏의 열에 있어야 한다: 복합 FK)."""
    return [make_column(key) for key in ORDERS]


def make_cell(  # noqa: PLR0913, PLR0917 - 셀의 독립 필드
    owner: UserId,
    year: int = 2026,
    month: int = 8,
    key: str = "pipeline",
    count: int = 1,
    amount: int = 100,
) -> SnapshotCell:
    from app.domain.forecast.snapshot import SnapshotCell  # noqa: PLC0415 - 구현 지연 import

    return SnapshotCell(
        revenue_year=year,
        revenue_month=month,
        owner_id=owner,
        forecast_key=key,
        tally=Tally(count, amount),
    )


def make_snapshot(
    period: YearMonth,
    *cells: SnapshotCell,
    taken_at: datetime = TAKEN_AT,
    columns: Sequence[SnapshotColumn] | None = None,
) -> ForecastSnapshot:
    from app.domain.forecast.snapshot import ForecastSnapshot  # noqa: PLC0415 - 구현 지연 import

    return ForecastSnapshot(
        period=period,
        taken_at=taken_at,
        columns=list(default_columns() if columns is None else columns),
        cells=list(cells),
    )


@asynccontextmanager
async def open_snapshot_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[SnapshotCase]:
    if implementation == "fake":
        uow = FakeUnitOfWork()
        yield SnapshotCase(uow.forecast_snapshots, uow.users)
        return
    from app.infra.db.forecast_repository import SqlForecastSnapshotRepository  # noqa: PLC0415
    from app.infra.db.user_repository import SqlUserRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield SnapshotCase(SqlForecastSnapshotRepository(session), SqlUserRepository(session))
