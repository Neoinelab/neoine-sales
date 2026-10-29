"""FakeUseCases에 섞어 쓰는 파트너 Activity 유스케이스 조립(mixin).

유스케이스 모듈은 사용 시점에 가져온다. FakeUseCases는 미팅과 무관한 테스트도 쓰므로, 모듈 수준
import는 구현이 없는 동안 그 테스트의 수집까지 막는다. 메서드 이름은 web의 `UseCaseProvider`
계약이다: register_partner_meetings, update_partner_meeting, delete_partner_meeting,
list_partner_meetings, list_partner_deal_choices.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.partner_meeting.delete_partner_meeting import DeletePartnerMeeting
    from app.application.partner_meeting.list_partner_deal_choices import ListPartnerDealChoices
    from app.application.partner_meeting.list_partner_meetings import ListPartnerMeetings
    from app.application.partner_meeting.register_partner_meetings import RegisterPartnerMeetings
    from app.application.partner_meeting.update_partner_meeting import UpdatePartnerMeeting

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class PartnerMeetingUseCases:
    """`_meeting_uow_factory()`와 `clock`을 가진 클래스에 섞는다."""

    clock: Clock

    def _meeting_uow_factory(self) -> UnitOfWorkFactory:
        raise NotImplementedError

    def register_partner_meetings(self) -> RegisterPartnerMeetings:
        from app.application.partner_meeting.register_partner_meetings import (  # noqa: PLC0415
            RegisterPartnerMeetings,
        )

        return RegisterPartnerMeetings(self._meeting_uow_factory(), self.clock)

    def update_partner_meeting(self) -> UpdatePartnerMeeting:
        from app.application.partner_meeting.update_partner_meeting import (  # noqa: PLC0415
            UpdatePartnerMeeting,
        )

        return UpdatePartnerMeeting(self._meeting_uow_factory(), self.clock)

    def delete_partner_meeting(self) -> DeletePartnerMeeting:
        from app.application.partner_meeting.delete_partner_meeting import (  # noqa: PLC0415
            DeletePartnerMeeting,
        )

        return DeletePartnerMeeting(self._meeting_uow_factory())

    def list_partner_meetings(self) -> ListPartnerMeetings:
        from app.application.partner_meeting.list_partner_meetings import (  # noqa: PLC0415
            ListPartnerMeetings,
        )

        return ListPartnerMeetings(self._meeting_uow_factory())

    def list_partner_deal_choices(self) -> ListPartnerDealChoices:
        from app.application.partner_meeting.list_partner_deal_choices import (  # noqa: PLC0415
            ListPartnerDealChoices,
        )

        return ListPartnerDealChoices(self._meeting_uow_factory())
