from typing import TYPE_CHECKING

from app.application.partner_meeting.checker import MeetingChecker
from app.application.ports.partner_meeting_repository import PartnerMeetingRecord
from app.domain.deal.code import DealCode
from app.domain.partner_meeting.values import MeetingSubject

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.partner_meeting.inputs import MeetingInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.partner_meeting.values import PartnerMeetingId


class UpdatePartnerMeeting:
    """미팅 기록을 고친다. 판정 순서는 없음(404) -> 권한(403) -> 입력(422).

    회사나 Deal을 바꿀 때만 Deal 연결을 다시 확인한다. 바뀐 값이 없으면 저장하지 않는다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, meeting_id: PartnerMeetingId, data: MeetingInput, actor: Actor
    ) -> PartnerMeetingRecord:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            current = await uow.partner_meetings.get(meeting_id, for_update=True)
            meeting = current.meeting
            meeting.ensure_editable_by(actor.user_id, actor.role)
            code = DealCode.parse_or_none(data.deal_code)
            link = code is None or meeting.needs_link_check(
                MeetingSubject(data.partner_company, code)
            )
            row = await MeetingChecker(uow).check_update(data, current, link=link)
            changed = meeting.revise(
                subject=row.subject, meeting_date=row.meeting_date, content=row.content, now=now
            )
            if changed:
                await uow.partner_meetings.update(meeting)
                await uow.commit()
        return PartnerMeetingRecord(meeting, row.deal_name)
