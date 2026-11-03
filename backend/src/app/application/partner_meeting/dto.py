from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.partner_meeting.entities import PartnerMeeting


@dataclass(frozen=True, slots=True)
class PartnerMeetingPage:
    items: Sequence[PartnerMeeting]
    total: int
    offset: int
    limit: int
