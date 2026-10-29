from typing import TYPE_CHECKING

from app.application.partner_meeting.dto import PartnerMeetingPage

if TYPE_CHECKING:
    from app.application.ports.partner_meeting_repository import PartnerMeetingQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListPartnerMeetings:
    """조건에 맞는 미팅 한 페이지와 전체 건수."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: PartnerMeetingQuery) -> PartnerMeetingPage:
        async with self._uow_factory() as uow:
            items = await uow.partner_meetings.search(query)
            total = await uow.partner_meetings.count(query)
        return PartnerMeetingPage(items=items, total=total, offset=query.offset, limit=query.limit)
