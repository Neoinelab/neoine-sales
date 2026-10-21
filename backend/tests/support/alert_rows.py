"""head 스키마(BIGINT id)의 alert_settings에 원시 SQL로 행을 넣는 도우미(제약 검증용)."""

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_ALERT_SETTINGS = (
    "insert into alert_settings (id, stale_days, updated_at, updated_by_user_id)"
    " values (:id, :stale_days, now(), :updated_by)"
)


async def insert_alert_settings(
    session: AsyncSession, updated_by: int, **overrides: object
) -> None:
    """경고 기준 한 행(기본 id=1, 14일). overrides는 INSERT 파라미터를 덮어쓴다."""
    params: dict[str, object] = {
        "id": 1,
        "stale_days": 14,
        "updated_by": updated_by,
        **overrides,
    }
    await session.execute(text(INSERT_ALERT_SETTINGS), params)
