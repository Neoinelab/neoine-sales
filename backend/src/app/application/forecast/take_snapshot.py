from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.code.values import CodeKind
from app.domain.common.business_date import business_date
from app.domain.forecast.snapshot import (
    ForecastSnapshot,
    SnapshotCell,
    SnapshotColumn,
    default_snapshot_month,
    ensure_snapshot_allowed,
)

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.forecast.snapshot import YearMonth


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    period: YearMonth
    taken_at: datetime
    cell_count: int
    replaced: bool


class TakeForecastSnapshot:
    """모든 Deal의 현재 Forecast 집계를 기준 월 스냅숏으로 저장(같은 월이면 대체)한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, target: YearMonth | None = None) -> SnapshotResult:
        now = self._clock.now()
        today = business_date(now)
        period = target or default_snapshot_month(today)
        ensure_snapshot_allowed(period, today)
        async with self._uow_factory() as uow:
            await uow.forecast_snapshots.lock_period(period)
            replaced = await uow.forecast_snapshots.get(period) is not None
            columns = [
                SnapshotColumn(c.key.value, c.name, c.outcome, c.order)
                for c in await uow.codes.list(CodeKind.FORECAST)
            ]
            cells = [
                SnapshotCell(
                    revenue_year=b.revenue_year,
                    revenue_month=b.revenue_month,
                    owner_id=b.owner_id,
                    forecast_key=b.forecast_key,
                    tally=b.tally,
                )
                for b in await uow.forecast.tally_by_month()
            ]
            await uow.forecast_snapshots.replace(
                ForecastSnapshot(period=period, taken_at=now, columns=columns, cells=cells)
            )
            await uow.commit()
        return SnapshotResult(period, now, len(cells), replaced)
