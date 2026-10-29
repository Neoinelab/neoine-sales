from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.application.ports.deal_repository import SortOrder
from app.application.ports.pagination import check_page
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, optional_text
from app.domain.partner_meeting.values import check_meeting_date

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from app.domain.deal.code import DealCode
    from app.domain.partner_meeting.entities import PartnerMeeting
    from app.domain.partner_meeting.values import PartnerMeetingId
    from app.domain.user.value_objects import UserId

CONTENT_KEYWORD_MAX = 100
TEXT_FILTER_MAX = 200
DEFAULT_MEETING_LIMIT = 10
DATE_RANGE_REVERSED = "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다."


class PartnerMeetingSort(StrEnum):
    MEETING_DATE = "meeting_date"
    PARTNER = "partner"
    DEAL = "deal"
    CONTENT = "content"
    AUTHOR = "author"


@dataclass(frozen=True, slots=True)
class PartnerMeetingQuery:
    """미팅 목록 조건(AND). 텍스트는 앞뒤 공백을 지우고 비면 None이다.

    partner는 저장된 회사명, deal은 현재 Deal 이름 또는 code, content는 미팅 내용의 부분 일치다.
    날짜 범위는 양끝을 포함하며 시작이 끝보다 늦으면 InvalidValueError다.
    """

    partner: str | None = None
    deal: str | None = None
    content: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    author_user_id: UserId | None = None
    sort: PartnerMeetingSort = PartnerMeetingSort.MEETING_DATE
    order: SortOrder = SortOrder.DESC
    offset: int = 0
    limit: int = DEFAULT_MEETING_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        assign(
            self,
            partner=optional_text(self.partner, "파트너", max_length=TEXT_FILTER_MAX),
            deal=optional_text(self.deal, "Deal", max_length=TEXT_FILTER_MAX),
            content=optional_text(self.content, "미팅 내용", max_length=CONTENT_KEYWORD_MAX),
        )
        for day in (self.date_from, self.date_to):
            if day is not None:
                check_meeting_date(day)
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise InvalidValueError(DATE_RANGE_REVERSED)


@dataclass(frozen=True, slots=True)
class PartnerMeetingRecord:
    """미팅과 읽는 시점의 Deal 이름."""

    meeting: PartnerMeeting
    deal_name: str


@dataclass(frozen=True, slots=True)
class PartnerDealChoice:
    code: DealCode
    name: str
    customer_company: str


class PartnerMeetingRepository(Protocol):
    """미팅 기록 저장소. 삭제는 물리 삭제이고 Deal을 지우면 미팅도 함께 지워진다."""

    async def add(self, meeting: PartnerMeeting) -> None:
        """같은 id는 AlreadyExistsError, Deal이 없으면 DealNotFoundError, 작성자가 없으면
        InvalidReferenceError("사용자")."""
        ...

    async def get(
        self, meeting_id: PartnerMeetingId, *, for_update: bool = False
    ) -> PartnerMeetingRecord:
        """없으면 PartnerMeetingNotFoundError. for_update면 트랜잭션 끝까지 행을 잠근다."""
        ...

    async def update(self, meeting: PartnerMeeting) -> None:
        """subject·meeting_date·content·updated_at만 저장한다. 없으면 PartnerMeetingNotFoundError,
        새 Deal이 없으면 DealNotFoundError."""
        ...

    async def delete(self, meeting_id: PartnerMeetingId) -> None:
        """물리 삭제. 없으면 PartnerMeetingNotFoundError."""
        ...

    async def search(self, query: PartnerMeetingQuery) -> Sequence[PartnerMeetingRecord]:
        """조건(AND)에 맞는 한 페이지.

        텍스트는 대소문자 무시 부분 일치이고 `%`·`_`·`\\`는 글자 그대로다.
        정렬: meeting_date는 (날짜, id)를 방향대로. partner·deal·content·author는 주 키
        lower(...) COLLATE "C"를 방향대로 -> 미팅 날짜 내림차순 -> id 내림차순(동률 규칙은 방향과
        무관). author는 표시 이름(없으면 login_id, 퇴사자 포함), deal은 현재 이름이다.
        """
        ...

    async def count(self, query: PartnerMeetingQuery) -> int:
        """페이지와 무관한 조건에 맞는 전체 건수."""
        ...

    async def deal_choices(self, company: str) -> Sequence[PartnerDealChoice]:
        """활성 파트너 링크(unlinked_at 없음)의 연락처 회사명이 company와 대소문자 무시로 같은
        Deal 전부(Forecast 무관). lower(name) COLLATE "C", code 오름차순. 없으면 빈 목록."""
        ...
