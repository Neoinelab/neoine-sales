"""Forecast 월말 스냅숏 저장소(ForecastSnapshotRepository Port의 SQLAlchemy 구현).

기준 월(연, 월)당 헤더 1행 + 열(그 시점 코드 목록) + 셀. 이 저장소는 변환과 저장만 하고
어떤 월을 만들 수 있는지는 판단하지 않는다(도메인·유스케이스 몫).
"""

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.application.ports.forecast_repository import SnapshotInfo
from app.domain.code.values import ForecastOutcome
from app.domain.forecast.snapshot import ForecastSnapshot, SnapshotCell, SnapshotColumn, YearMonth
from app.domain.forecast.summary import Tally
from app.domain.user.value_objects import UserId
from app.infra.db.models_forecast import (
    ForecastSnapshotCellRow,
    ForecastSnapshotColumnRow,
    ForecastSnapshotRow,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

# pg_advisory_xact_lock(bigint) 키: 상위 32비트는 이 용도의 고정 값('FCST'), 하위는 기준 월.
_LOCK_NAMESPACE = 0x46435354 << 32
_COLUMN_FK = "fk_forecast_snapshot_cells_snapshot_id_snapshot_columns"
_STALE_COLUMNS_MESSAGE = (
    "스냅숏을 만드는 사이 Forecast 코드가 바뀌어 저장하지 못했습니다. 다시 실행하세요."
)


def _lock_key(period: YearMonth) -> int:
    return _LOCK_NAMESPACE | (period.year * 100 + period.month)


class SqlForecastSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_period(self, period: YearMonth) -> None:
        """같은 기준 월의 실행을 직렬화한다. 트랜잭션 advisory lock이라 commit/rollback에 풀린다.

        헤더가 아직 없어도 잠글 수 있고, 잠금을 얻은 뒤의 질의는 앞선 실행의 commit을 본다.
        """
        await self._session.execute(select(func.pg_advisory_xact_lock(_lock_key(period))))

    async def replace(self, snapshot: ForecastSnapshot) -> None:
        period = snapshot.period
        header_id = await self._header_id(period)
        if header_id is None:
            header_id = (
                await self._session.execute(
                    insert(ForecastSnapshotRow)
                    .values(
                        snapshot_year=period.year,
                        snapshot_month=period.month,
                        taken_at=snapshot.taken_at,
                    )
                    .returning(ForecastSnapshotRow.id)
                )
            ).scalar_one()
        else:
            await self._session.execute(
                delete(ForecastSnapshotCellRow).where(
                    ForecastSnapshotCellRow.snapshot_id == header_id
                )
            )
            await self._session.execute(
                delete(ForecastSnapshotColumnRow).where(
                    ForecastSnapshotColumnRow.snapshot_id == header_id
                )
            )
            await self._session.execute(
                update(ForecastSnapshotRow)
                .where(ForecastSnapshotRow.id == header_id)
                .values(taken_at=snapshot.taken_at)
            )
        await self._insert_children(header_id, snapshot)

    async def get(self, period: YearMonth) -> ForecastSnapshot | None:
        header = (
            await self._session.execute(
                select(ForecastSnapshotRow).where(
                    ForecastSnapshotRow.snapshot_year == period.year,
                    ForecastSnapshotRow.snapshot_month == period.month,
                )
            )
        ).scalar_one_or_none()
        if header is None:
            return None
        columns = (
            await self._session.scalars(
                select(ForecastSnapshotColumnRow)
                .where(ForecastSnapshotColumnRow.snapshot_id == header.id)
                .order_by(ForecastSnapshotColumnRow.forecast_order)
            )
        ).all()
        cells = (
            await self._session.scalars(
                select(ForecastSnapshotCellRow).where(
                    ForecastSnapshotCellRow.snapshot_id == header.id
                )
            )
        ).all()
        return ForecastSnapshot(
            period=period,
            taken_at=header.taken_at,
            columns=[
                SnapshotColumn(
                    c.forecast_key,
                    c.forecast_name,
                    ForecastOutcome(c.forecast_outcome),
                    c.forecast_order,
                )
                for c in columns
            ],
            cells=[
                SnapshotCell(
                    c.revenue_year,
                    c.revenue_month,
                    UserId(c.owner_user_id),
                    c.forecast_key,
                    Tally(c.deal_count, c.amount),
                )
                for c in cells
            ],
        )

    async def list_periods(self) -> Sequence[SnapshotInfo]:
        rows = await self._session.execute(
            select(
                ForecastSnapshotRow.snapshot_year,
                ForecastSnapshotRow.snapshot_month,
                ForecastSnapshotRow.taken_at,
            ).order_by(
                ForecastSnapshotRow.snapshot_year.desc(), ForecastSnapshotRow.snapshot_month.desc()
            )
        )
        return [SnapshotInfo(YearMonth(year, month), taken_at) for year, month, taken_at in rows]

    async def _header_id(self, period: YearMonth) -> int | None:
        return (
            await self._session.execute(
                select(ForecastSnapshotRow.id).where(
                    ForecastSnapshotRow.snapshot_year == period.year,
                    ForecastSnapshotRow.snapshot_month == period.month,
                )
            )
        ).scalar_one_or_none()

    async def _insert_children(self, header_id: int, snapshot: ForecastSnapshot) -> None:
        if snapshot.columns:
            await self._session.execute(
                insert(ForecastSnapshotColumnRow),
                [
                    {
                        "snapshot_id": header_id,
                        "forecast_key": c.key,
                        "forecast_name": c.name,
                        "forecast_outcome": c.outcome.value,
                        "forecast_order": c.order,
                    }
                    for c in snapshot.columns
                ],
            )
        if not snapshot.cells:
            return
        try:
            await self._session.execute(
                insert(ForecastSnapshotCellRow),
                [
                    {
                        "snapshot_id": header_id,
                        "revenue_year": c.revenue_year,
                        "revenue_month": c.revenue_month,
                        "owner_user_id": int(c.owner_id),
                        "forecast_key": c.forecast_key,
                        "deal_count": c.tally.count,
                        "amount": c.tally.amount,
                    }
                    for c in snapshot.cells
                ],
            )
        except IntegrityError as error:
            # 열 목록을 읽은 뒤 새 코드로 옮겨진 Deal이 있으면 복합 FK가 거절한다(호출한 쪽이 롤백).
            if _COLUMN_FK not in str(error.orig):
                raise
            raise RuntimeError(_STALE_COLUMNS_MESSAGE) from error
