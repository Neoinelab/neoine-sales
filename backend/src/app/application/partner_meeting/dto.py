from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.partner_meeting_repository import PartnerMeetingRecord


@dataclass(frozen=True, slots=True)
class PartnerMeetingPage:
    items: Sequence[PartnerMeetingRecord]
    total: int
    offset: int
    limit: int
