"""Deal 집계 질의: 코드·Label별 건수, Vendor별 건수, 삭제 영향 건수."""

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.bant.values import BantLabelId
from app.domain.vendor.values import VendorId
from app.infra.db.models import DealActionRow
from app.infra.db.models_attachment import DealAttachmentRow
from app.infra.db.models_deal import DealBantLabelRow, DealHistoryRow, DealRow

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import InstrumentedAttribute


async def _counts[KeyT](
    session: AsyncSession, column: InstrumentedAttribute[KeyT]
) -> dict[KeyT, int]:
    statement = select(column, func.count()).group_by(column)
    return {key: int(count) for key, count in await session.execute(statement)}


async def count_by_status(session: AsyncSession) -> Mapping[str, int]:
    return await _counts(session, DealRow.status_key)


async def count_by_forecast(session: AsyncSession) -> Mapping[str, int]:
    return await _counts(session, DealRow.forecast_key)


async def count_by_bant_label(session: AsyncSession) -> Mapping[BantLabelId, int]:
    counts = await _counts(session, DealBantLabelRow.label_id)
    return {BantLabelId(label_id): count for label_id, count in counts.items()}


async def count_by_vendor(session: AsyncSession) -> Mapping[VendorId, int]:
    counts = await _counts(session, DealRow.vendor_id)
    return {VendorId(key): count for key, count in counts.items() if key is not None}


async def deletion_impact(session: AsyncSession, deal_id: int) -> DealDeletionImpact:
    """Deal을 지우면 함께 지워지는 이력·활동 건수·첨부 건수."""
    history = (
        select(func.count()).select_from(DealHistoryRow).where(DealHistoryRow.deal_id == deal_id)
    )
    actions = (
        select(func.count()).select_from(DealActionRow).where(DealActionRow.deal_id == deal_id)
    )
    attachments = (
        select(func.count())
        .select_from(DealAttachmentRow)
        .where(DealAttachmentRow.deal_id == deal_id)
    )
    return DealDeletionImpact(
        history_count=int(await session.scalar(history) or 0),
        action_count=int(await session.scalar(actions) or 0),
        attachment_count=int(await session.scalar(attachments) or 0),
    )
