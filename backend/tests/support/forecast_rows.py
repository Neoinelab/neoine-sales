"""head 스키마의 Forecast 스냅숏 테이블에 원시 SQL로 행을 넣는 도우미(제약 검증용, P6 R2)."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

TAKEN_AT = datetime(2026, 10, 1, 0, 5, tzinfo=UTC)
INSERT_SNAPSHOT = (
    "insert into forecast_snapshots (snapshot_year, snapshot_month, taken_at)"
    " values (:year, :month, :taken_at) returning id"
)
INSERT_COLUMN = (
    "insert into forecast_snapshot_columns (snapshot_id, forecast_key, forecast_name,"
    " forecast_outcome, forecast_order)"
    " values (:snapshot_id, :forecast_key, :forecast_name, :forecast_outcome, :forecast_order)"
    " returning id"
)
INSERT_CELL = (
    "insert into forecast_snapshot_cells (snapshot_id, revenue_year, revenue_month,"
    " owner_user_id, forecast_key, deal_count, amount)"
    " values (:snapshot_id, :revenue_year, :revenue_month, :owner_user_id, :forecast_key,"
    " :deal_count, :amount) returning id"
)


async def insert_snapshot(session: AsyncSession, **overrides: object) -> int:
    """기준 월 한 행(기본 2026-09). overrides는 INSERT 파라미터를 덮어쓴다."""
    params: dict[str, object] = {"year": 2026, "month": 9, "taken_at": TAKEN_AT, **overrides}
    return int((await session.execute(text(INSERT_SNAPSHOT), params)).scalar_one())


async def insert_column(session: AsyncSession, snapshot_id: int, **overrides: object) -> int:
    """열(저장 당시의 코드) 한 행(기본 pipeline/Pipeline/open/1). overrides는 덮어쓴다."""
    params: dict[str, object] = {
        "snapshot_id": snapshot_id,
        "forecast_key": "pipeline",
        "forecast_name": "Pipeline",
        "forecast_outcome": "open",
        "forecast_order": 1,
        **overrides,
    }
    return int((await session.execute(text(INSERT_COLUMN), params)).scalar_one())


async def insert_cell(
    session: AsyncSession, snapshot_id: int, owner_user_id: int, **overrides: object
) -> int:
    """셀 한 행(기본 2026-10, pipeline, 1건 100원). 같은 키의 열이 그 스냅숏에 먼저 있어야 한다."""
    params: dict[str, object] = {
        "snapshot_id": snapshot_id,
        "revenue_year": 2026,
        "revenue_month": 10,
        "owner_user_id": owner_user_id,
        "forecast_key": "pipeline",
        "deal_count": 1,
        "amount": 100,
        **overrides,
    }
    return int((await session.execute(text(INSERT_CELL), params)).scalar_one())
