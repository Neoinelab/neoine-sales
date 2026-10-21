"""Deal에 딸린 행(파트너 링크, BANT 선택)의 읽기·동기화. SqlDealRepository가 쓴다."""

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.infra.db import deal_mapping
from app.infra.db.models_deal import DealBantLabelRow, DealPartnerRow

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.deal.entities import Deal, PartnerLink
    from app.infra.db.models_deal import DealRow


def partner_row(deal_id: int, link: PartnerLink) -> DealPartnerRow:
    """파트너 링크 행. id는 도메인이 모르므로 DB 기본값(IDENTITY)에 맡긴다."""
    return DealPartnerRow(
        deal_id=deal_id,
        contact_id=link.contact_id,
        linked_at=link.linked_at,
        unlinked_at=link.unlinked_at,
    )


def bant_rows(deal: Deal, deal_id: int, skip: Mapping[str, object]) -> list[DealBantLabelRow]:
    """선택된 구분의 행. skip에 이미 있는 구분은 만들지 않는다."""
    return [
        DealBantLabelRow(deal_id=deal_id, category=category, label_id=label_id)
        for category, label_id in deal_mapping.bant_pairs(deal).items()
        if category not in skip
    ]


async def partner_rows_of(
    session: AsyncSession, deal_ids: Collection[int]
) -> Sequence[DealPartnerRow]:
    statement = (
        select(DealPartnerRow)
        .where(DealPartnerRow.deal_id.in_(deal_ids))
        .order_by(DealPartnerRow.linked_at, DealPartnerRow.id)
        .execution_options(populate_existing=True)
    )
    return (await session.scalars(statement)).all()


async def bant_rows_of(
    session: AsyncSession, deal_ids: Collection[int]
) -> Sequence[DealBantLabelRow]:
    statement = (
        select(DealBantLabelRow)
        .where(DealBantLabelRow.deal_id.in_(deal_ids))
        .execution_options(populate_existing=True)
    )
    return (await session.scalars(statement)).all()


async def sync_partners(session: AsyncSession, deal: Deal, deal_id: int) -> None:
    """링크는 (연락처, 연결 시각)으로 식별한다. 해제 시각 갱신을 먼저 보낸 뒤 새 링크를 넣는다."""
    stored = {
        (row.contact_id, row.linked_at): row for row in await partner_rows_of(session, [deal_id])
    }
    fresh: list[DealPartnerRow] = []
    for link in deal.partner_links:
        row = stored.get((link.contact_id, link.linked_at))
        if row is None:
            fresh.append(partner_row(deal_id, link))
        else:
            row.unlinked_at = link.unlinked_at
    await session.flush()  # 기존 활성 링크를 해제한 뒤에야 새 활성 링크를 넣을 수 있다
    session.add_all(fresh)


async def sync_bant(session: AsyncSession, deal: Deal, deal_id: int) -> None:
    """구분별로 선택을 교체한다(선택 해제는 행 삭제)."""
    stored = {row.category: row for row in await bant_rows_of(session, [deal_id])}
    wanted = deal_mapping.bant_pairs(deal)
    for category, row in stored.items():
        if category in wanted:
            row.label_id = wanted[category]
        else:
            await session.delete(row)
    session.add_all(bant_rows(deal, deal_id, stored))


async def hydrate(session: AsyncSession, rows: Sequence[DealRow]) -> list[Deal]:
    """행 목록을 파트너 링크·BANT 선택과 함께 엔티티로 만든다(자식은 한 번에 읽는다)."""
    deal_ids = [row.id for row in rows]
    if not deal_ids:
        return []
    partners: dict[int, list[DealPartnerRow]] = {}
    for link in await partner_rows_of(session, deal_ids):
        partners.setdefault(link.deal_id, []).append(link)
    chosen: dict[int, list[DealBantLabelRow]] = {}
    for choice in await bant_rows_of(session, deal_ids):
        chosen.setdefault(choice.deal_id, []).append(choice)
    return [
        deal_mapping.to_entity(row, partners.get(row.id, []), chosen.get(row.id, []))
        for row in rows
    ]
