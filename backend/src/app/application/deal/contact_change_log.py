"""연락처 정보가 바뀌었을 때 그 연락처를 참조하는 모든 Deal의 History에 한 건씩 남긴다."""

from typing import TYPE_CHECKING

from app.domain.deal.history import (
    DealHistoryEntry,
    HistoryCategory,
    HistoryDraft,
    contact_change_target,
    contact_info_text,
)

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactDetails
    from app.domain.deal.code import DealCode
    from app.domain.user.value_objects import UserId


async def log_contact_change(
    uow: UnitOfWork,
    contact: Contact,
    before: ContactDetails,
    changed_by: UserId,
    now: datetime,
) -> frozenset[DealCode]:
    """고객 참조와 모든 파트너 링크(비활성 포함)의 Deal에 contact History를 남긴다.

    같은 Deal이 같은 역할로 여러 번 참조해도 한 건이다. 해당 Deal의 수정 시각도 갱신하고, 갱신한
    Deal의 code 집합을 돌려준다(같은 트랜잭션에서 그 Deal을 저장하는 쪽이 시각을 맞추도록).
    """
    found = await uow.deals.references_of_contact(contact.id)
    references = list(dict.fromkeys((ref.deal_code, ref.role) for ref in found))
    if not references:
        return frozenset()
    before_text = contact_info_text(before)
    after_text = contact_info_text(contact.details)
    entries = [
        DealHistoryEntry(
            id=None,
            deal_code=code,
            changed_at=now,
            changed_by=changed_by,
            draft=HistoryDraft(
                HistoryCategory.CONTACT,
                contact_change_target(role, contact.details),
                before_text,
                after_text,
            ),
        )
        for code, role in references
    ]
    await uow.deal_history.add_many(entries)
    codes = frozenset(code for code, _ in references)
    await uow.deals.touch(codes, now)
    return codes
