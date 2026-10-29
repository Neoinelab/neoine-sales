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
    PartnerDealChoice,
    PartnerMeetingQuery,
    PartnerMeetingRecord,
    PartnerMeetingSort,
)
from app.domain.contact.values import COMPANY_MAX
from app.web.schemas.common import CountedPage, RequestModel
from app.web.schemas.ids import QueryId
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef

DEAL_CODE_MAX = 50
MAX_ITEMS = 50


class MeetingItemRequest(RequestModel):
    partner_company: Annotated[str, Field(max_length=COMPANY_MAX)]
    deal_code: Annotated[str, Field(max_length=DEAL_CODE_MAX)]
    meeting_date: date
    content: str

    def to_input(self) -> MeetingInput:
        return MeetingInput(**self.model_dump())


class MeetingBatchRequest(RequestModel):
    items: Annotated[list[MeetingItemRequest], Field(min_length=1, max_length=MAX_ITEMS)]

    def to_inputs(self) -> list[MeetingInput]:
        return [item.to_input() for item in self.items]


class MeetingDealResponse(BaseModel):
    code: str
    name: str


class PartnerMeetingResponse(BaseModel):
    id: int
    partner_company: str
    deal: MeetingDealResponse
    meeting_date: date
    content: str
    author: UserRef
    created_at: ServerDateTime
    updated_at: ServerDateTime

    @classmethod
    def from_record(
        cls, record: PartnerMeetingRecord, refs: Mapping[UserId, DomainUserRef]
    ) -> PartnerMeetingResponse:
        meeting = record.meeting
        return cls(
            id=meeting.id,
            partner_company=meeting.subject.partner_company,
            deal=MeetingDealResponse(code=meeting.subject.deal_code.value, name=record.deal_name),
            meeting_date=meeting.meeting_date,
            content=meeting.content.value,
            author=ref_of(refs, meeting.author_user_id),
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
        )


def meeting_responses(
    records: Sequence[PartnerMeetingRecord], refs: Mapping[UserId, DomainUserRef]
) -> list[PartnerMeetingResponse]:
    return [PartnerMeetingResponse.from_record(record, refs) for record in records]


class MeetingBatchResponse(BaseModel):
    items: list[PartnerMeetingResponse]


PartnerMeetingPage = CountedPage[PartnerMeetingResponse]


class PartnerMeetingSearchParams(RequestModel):
    """목록 쿼리 파라미터. 알 수 없는 파라미터는 422다."""

    partner: Annotated[str | None, Field(max_length=TEXT_FILTER_MAX)] = None
    deal: Annotated[str | None, Field(max_length=TEXT_FILTER_MAX)] = None
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


class DealOptionsParams(RequestModel):
    company: Annotated[str, Field(max_length=COMPANY_MAX)]


class DealOptionResponse(BaseModel):
    code: str
    name: str
    customer_company: str

    @classmethod
    def from_choice(cls, choice: PartnerDealChoice) -> DealOptionResponse:
        return cls(
            code=choice.code.value, name=choice.name, customer_company=choice.customer_company
        )


class DealOptionsResponse(BaseModel):
    items: list[DealOptionResponse]
