"""Deal 업무 키(deal_code) -> 내부 대리 키(deals.id) 변환. 도메인은 deals.id를 모른다."""

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def deal_id_of(session: AsyncSession, code: str) -> int | None:
    """code의 Deal 행 id. Deal이 없으면 None."""
    return await session.scalar(select(DealRow.id).where(DealRow.deal_code == code))


async def deal_row_of(
    session: AsyncSession, code: str, *, for_update: bool = False
) -> DealRow | None:
    statement = select(DealRow).where(DealRow.deal_code == code)
    if for_update:
        statement = statement.with_for_update()
    return (
        await session.scalars(statement.execution_options(populate_existing=True))
    ).one_or_none()
