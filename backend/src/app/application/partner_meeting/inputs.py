from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


@dataclass(frozen=True, slots=True)
class MeetingInput:
    """미팅 한 건의 입력. 검증은 MeetingChecker가 한다."""

    partner_company: str
    deal_code: str
    meeting_date: date
    content: str
