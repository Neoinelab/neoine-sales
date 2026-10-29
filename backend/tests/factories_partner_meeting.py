"""파트너 Activity 테스트용 생성 도우미. 기본은 유효한 더미 값이다.

팩토리는 연결 검사·권한을 거치지 않고 필드로 직접 만든다(규칙 자체를 검증하는 테스트가 팩토리에
기대지 않도록). 도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이
막히지 않게).

계약(구현 담당이 맞춘다): `PartnerMeeting.record(entity_id=, subject=, meeting_date=, content=,
author_user_id=, now=)`는 키워드 전용이고, `MeetingSubject(partner_company, deal_code)`,
`MeetingContent(value)`는 위치 인자로 만든다.
"""

from datetime import date
from typing import TYPE_CHECKING

from tests.factories import NOW, make_deal_code
from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.partner_meeting.entities import PartnerMeeting
    from app.domain.partner_meeting.values import MeetingSubject

    from app.domain.deal.code import DealCode
    from app.domain.user.value_objects import UserId

DEFAULT_COMPANY = "한빛파트너스"
DEFAULT_DATE = date(2026, 10, 1)


def make_subject(
    company: str = DEFAULT_COMPANY, deal_code: DealCode | None = None
) -> MeetingSubject:
    from app.domain.partner_meeting.values import MeetingSubject  # noqa: PLC0415

    return MeetingSubject(company, deal_code or make_deal_code())


def make_meeting(  # noqa: PLR0913 - 미팅 생성에 필요한 값이 모두 독립적인 선택지
    *,
    deal_code: DealCode | None = None,
    company: str = DEFAULT_COMPANY,
    meeting_date: date = DEFAULT_DATE,
    content: str = "킥오프 미팅",
    author: UserId = ACTOR_ID,
    entity_id: int | None = None,
    now: datetime = NOW,
) -> PartnerMeeting:
    """저장하지 않은 미팅 기록(`PartnerMeeting.record`)."""
    from app.domain.partner_meeting.entities import PartnerMeeting  # noqa: PLC0415
    from app.domain.partner_meeting.values import MeetingContent, PartnerMeetingId  # noqa: PLC0415

    return PartnerMeeting.record(
        entity_id=PartnerMeetingId(new_id() if entity_id is None else entity_id),
        subject=make_subject(company, deal_code),
        meeting_date=meeting_date,
        content=MeetingContent(content),
        author_user_id=author,
        now=now,
    )
