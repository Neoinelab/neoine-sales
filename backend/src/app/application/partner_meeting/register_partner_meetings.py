from typing import TYPE_CHECKING

from app.application.ids import new_partner_meeting_id
from app.application.partner_meeting.checker import MeetingChecker
from app.application.ports.partner_meeting_repository import PartnerMeetingRecord
from app.domain.common.errors import InvalidValueError
from app.domain.partner_meeting.entities import PartnerMeeting
from app.domain.partner_meeting.errors import NO_ITEMS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.deal.inputs import Actor
    from app.application.partner_meeting.inputs import MeetingInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class RegisterPartnerMeetings:
    """미팅 기록을 한 트랜잭션으로 등록한다. 위반이 하나라도 있으면 아무것도 저장하지 않는다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, items: Sequence[MeetingInput], actor: Actor
    ) -> list[PartnerMeetingRecord]:
        if not items:
            raise InvalidValueError(NO_ITEMS)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            checked = await MeetingChecker(uow).check_all(items)
            records: list[PartnerMeetingRecord] = []
            for row in checked:
                meeting = PartnerMeeting.record(
                    entity_id=await new_partner_meeting_id(uow.ids),
                    subject=row.subject,
                    meeting_date=row.meeting_date,
                    content=row.content,
                    author_user_id=actor.user_id,
                    now=now,
                )
                await uow.partner_meetings.add(meeting)
                records.append(PartnerMeetingRecord(meeting, row.deal_name))
            await uow.commit()
        return records
