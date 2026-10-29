"""파트너 미팅 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.partner_meeting.delete_partner_meeting import DeletePartnerMeeting
from app.application.partner_meeting.list_partner_deal_choices import ListPartnerDealChoices
from app.application.partner_meeting.list_partner_meetings import ListPartnerMeetings
from app.application.partner_meeting.register_partner_meetings import RegisterPartnerMeetings
from app.application.partner_meeting.update_partner_meeting import UpdatePartnerMeeting

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class PartnerMeetingUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock

    def register_partner_meetings(self) -> RegisterPartnerMeetings:
        return RegisterPartnerMeetings(self._uow, self._clock)

    def update_partner_meeting(self) -> UpdatePartnerMeeting:
        return UpdatePartnerMeeting(self._uow, self._clock)

    def delete_partner_meeting(self) -> DeletePartnerMeeting:
        return DeletePartnerMeeting(self._uow)

    def list_partner_meetings(self) -> ListPartnerMeetings:
        return ListPartnerMeetings(self._uow)

    def list_partner_deal_choices(self) -> ListPartnerDealChoices:
        return ListPartnerDealChoices(self._uow)
