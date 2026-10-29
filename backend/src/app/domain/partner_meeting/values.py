"""파트너 미팅 기록의 값 객체: 내용, 날짜, 대상(파트너 회사와 Deal)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, NewType

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, check_date_in_bounds, reject_nul

if TYPE_CHECKING:
    from app.domain.deal.code import DealCode

PartnerMeetingId = NewType("PartnerMeetingId", int)

CONTENT_REQUIRED = "미팅 내용을 입력하세요."


@dataclass(frozen=True, slots=True)
class MeetingContent:
    """미팅 내용. 앞뒤 공백(줄바꿈 포함)을 제거하고 비면 거절하며 길이 제한은 없다."""

    value: str

    def __post_init__(self) -> None:
        reject_nul(self.value, "미팅 내용")
        text = self.value.strip()
        if not text:
            raise InvalidValueError(CONTENT_REQUIRED)
        assign(self, value=text)


def check_meeting_date(day: date) -> date:
    """1900-01-01~2999-12-31 사이의 시각 없는 날짜(미래 날짜 허용)."""
    if isinstance(day, datetime):
        raise InvalidValueError("미팅 날짜는 시각 없는 날짜여야 합니다")
    check_date_in_bounds(day, "미팅 날짜")
    return day


@dataclass(frozen=True, slots=True)
class MeetingSubject:
    """미팅의 대상: 파트너 회사(저장된 표기)와 Deal."""

    partner_company: str
    deal_code: DealCode

    def same_as(self, other: MeetingSubject) -> bool:
        """회사는 대소문자 무시, Deal은 code가 같으면 같다."""
        return (
            self.partner_company.lower() == other.partner_company.lower()
            and self.deal_code == other.deal_code
        )
