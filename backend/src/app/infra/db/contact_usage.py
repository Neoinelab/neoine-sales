"""연락처를 참조하는 Deal 수 집계. 연락처·Deal 저장소가 같은 질의를 공유한다."""

from typing import TYPE_CHECKING

from sqlalchemy import func, select, union

from app.domain.contact.values import ContactId
from app.infra.db.models_deal import DealPartnerRow, DealRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


async def deal_counts_by_contacts(
    session: AsyncSession, contact_ids: Sequence[ContactId]
) -> dict[ContactId, int]:
    """연락처별 참조 Deal 수. 요청한 id는 모두 키로 두고, 고객·파트너로 둘 다 참조해도 1건.

    파트너는 해제된 링크도 참조로 센다. (연락처, Deal) 쌍의 합집합이라 한 Deal은 연락처당 1건이다.
    """
    counts = dict.fromkeys(contact_ids, 0)
    if not counts:
        return counts
    pairs = union(
        select(DealRow.customer_id.label("contact_id"), DealRow.id.label("deal_id")),
        select(DealPartnerRow.contact_id, DealPartnerRow.deal_id),
    ).subquery()
    statement = (
        select(pairs.c.contact_id, func.count())
        .where(pairs.c.contact_id.in_(list(counts)))
        .group_by(pairs.c.contact_id)
    )
    for contact_id, count in await session.execute(statement):
        counts[ContactId(contact_id)] = int(count)
    return counts
