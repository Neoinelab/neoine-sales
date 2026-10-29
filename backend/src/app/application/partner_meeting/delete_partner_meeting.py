from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.partner_meeting.values import PartnerMeetingId


class DeletePartnerMeeting:
    """미팅 기록을 물리 삭제한다. 없으면 404, 작성자 본인·admin이 아니면 403."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, meeting_id: PartnerMeetingId, actor: Actor) -> None:
        async with self._uow_factory() as uow:
            current = await uow.partner_meetings.get(meeting_id)
            current.meeting.ensure_deletable_by(actor.user_id, actor.role)
            await uow.partner_meetings.delete(meeting_id)
            await uow.commit()
