from typing import TYPE_CHECKING

from app.domain.contact.values import ContactKind
from app.domain.partner_meeting.links import resolve_company

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.partner_meeting_repository import PartnerDealChoice
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListPartnerDealChoices:
    """파트너 회사에 활성으로 연결된 Deal 선택지. 등록된 파트너 회사가 아니면 빈 목록."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, company: str) -> Sequence[PartnerDealChoice]:
        async with self._uow_factory() as uow:
            resolved = resolve_company(company, await uow.contacts.companies(ContactKind.PARTNER))
            if resolved is None:
                return []
            return await uow.partner_meetings.deal_choices(resolved)
