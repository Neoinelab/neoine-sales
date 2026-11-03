"""파트너 Activity(미팅 기록) 요청·응답 스키마. 값 검증은 도메인이 하고 길이 상한은 문서용이다."""

from datetime import date
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field

from app.application.partner_meeting.inputs import MeetingInput
from app.application.ports.deal_repository import SortOrder
from app.application.ports.pagination import MAX_LIMIT
from app.application.ports.partner_meeting_repository import (
    CONTENT_KEYWORD_MAX,
    DEFAULT_MEETING_LIMIT,
    TEXT_FILTER_MAX,
    PartnerMeetingQuery,
    PartnerMeetingSort,
)
from app.domain.contact.values import COMPANY_MAX
from app.web.schemas.common import CountedPage, RequestModel
from app.web.schemas.ids import QueryId
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.domain.partner_meeting.entities import PartnerMeeting
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef

MAX_ITEMS = 50


class MeetingItemRequest(RequestModel):
    partner_company: Annotated[str, Field(max_length=COMPANY_MAX)]
    meeting_date: date
    content: str

    def to_input(self) -> MeetingInput:
        return MeetingInput(**self.model_dump())


class MeetingBatchRequest(RequestModel):
    items: Annotated[list[MeetingItemRequest], Field(min_length=1, max_length=MAX_ITEMS)]

    def to_inputs(self) -> list[MeetingInput]:
        return [item.to_input() for item in self.items]


class PartnerMeetingResponse(BaseModel):
    id: int
    partner_company: str
    meeting_date: date
    content: str
    author: UserRef
    created_at: ServerDateTime
    updated_at: ServerDateTime

    @classmethod
    def from_record(
        cls, meeting: PartnerMeeting, refs: Mapping[UserId, DomainUserRef]
    ) -> PartnerMeetingResponse:
        return cls(
            id=meeting.id,
            partner_company=meeting.partner_company,
            meeting_date=meeting.meeting_date,
            content=meeting.content.value,
            author=ref_of(refs, meeting.author_user_id),
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
        )


def meeting_responses(
    meetings: Sequence[PartnerMeeting], refs: Mapping[UserId, DomainUserRef]
) -> list[PartnerMeetingResponse]:
    return [PartnerMeetingResponse.from_record(meeting, refs) for meeting in meetings]


class MeetingBatchResponse(BaseModel):
    items: list[PartnerMeetingResponse]


PartnerMeetingPage = CountedPage[PartnerMeetingResponse]


class PartnerMeetingSearchParams(RequestModel):
    """목록 쿼리 파라미터. 알 수 없는 파라미터는 422다."""

    partner: Annotated[str | None, Field(max_length=TEXT_FILTER_MAX)] = None
    content: Annotated[str | None, Field(max_length=CONTENT_KEYWORD_MAX)] = None
    date_from: date | None = None
    date_to: date | None = None
    author_user_id: QueryId | None = None
    sort: PartnerMeetingSort = PartnerMeetingSort.MEETING_DATE
    order: SortOrder = SortOrder.DESC
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_MEETING_LIMIT

    def to_query(self) -> PartnerMeetingQuery:
        return PartnerMeetingQuery(**self.model_dump())
