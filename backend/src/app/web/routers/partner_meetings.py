"""파트너 Activity(미팅 기록): 목록·일괄 등록·수정·삭제·Deal 선택지.

읽기는 모든 역할, 쓰기는 WRITE 권한이다. 수정·삭제의 본인·admin 판정은 도메인이 한다.
"""

from typing import Annotated, Any

from fastapi import Query, Response, status

from app.application.deal.inputs import Actor
from app.domain.partner_meeting.values import PartnerMeetingId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM, READ_ERRORS
from app.web.schemas.ids import PathId
from app.web.schemas.partner_meeting import (
    DealOptionResponse,
    DealOptionsParams,
    DealOptionsResponse,
    MeetingBatchRequest,
    MeetingBatchResponse,
    MeetingItemRequest,
    PartnerMeetingPage,
    PartnerMeetingResponse,
    PartnerMeetingSearchParams,
    meeting_responses,
)
from app.web.schemas.user_ref import resolve_refs
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/partner-meetings", tags=["partner-meetings"])
CREATED = status.HTTP_201_CREATED
NO_CONTENT = status.HTTP_204_NO_CONTENT
LIST_ERRORS: dict[int | str, dict[str, Any]] = {422: PROBLEM}
CHANGE_ERRORS: dict[int | str, dict[str, Any]] = {404: PROBLEM, 422: PROBLEM}


def _actor(user: CurrentUser) -> Actor:
    return Actor(user_id=user.user_id, role=user.role)


@router.get("", response_model=PartnerMeetingPage, responses=LIST_ERRORS)
async def list_partner_meetings(
    params: Annotated[PartnerMeetingSearchParams, Query()], provider: Provider
) -> PartnerMeetingPage:
    page = await provider.list_partner_meetings().execute(params.to_query())
    refs = await resolve_refs(provider, [r.meeting.author_user_id for r in page.items])
    return PartnerMeetingPage(
        items=meeting_responses(page.items, refs),
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/deal-options", response_model=DealOptionsResponse, responses=LIST_ERRORS)
async def list_partner_deal_options(
    params: Annotated[DealOptionsParams, Query()], provider: Provider
) -> DealOptionsResponse:
    choices = await provider.list_partner_deal_choices().execute(params.company)
    return DealOptionsResponse(items=[DealOptionResponse.from_choice(c) for c in choices])


@router.post("", status_code=CREATED, response_model=MeetingBatchResponse, responses=LIST_ERRORS)
async def register_partner_meetings(
    body: MeetingBatchRequest, user: CurrentUser, provider: Provider
) -> MeetingBatchResponse:
    records = await provider.register_partner_meetings().execute(body.to_inputs(), _actor(user))
    refs = await resolve_refs(provider, [r.meeting.author_user_id for r in records])
    return MeetingBatchResponse(items=meeting_responses(records, refs))


@router.put("/{meeting_id}", response_model=PartnerMeetingResponse, responses=CHANGE_ERRORS)
async def update_partner_meeting(
    meeting_id: PathId, body: MeetingItemRequest, user: CurrentUser, provider: Provider
) -> PartnerMeetingResponse:
    record = await provider.update_partner_meeting().execute(
        PartnerMeetingId(meeting_id), body.to_input(), _actor(user)
    )
    refs = await resolve_refs(provider, [record.meeting.author_user_id])
    return PartnerMeetingResponse.from_record(record, refs)


@router.delete(
    "/{meeting_id}", status_code=NO_CONTENT, response_class=Response, responses=READ_ERRORS
)
async def delete_partner_meeting(meeting_id: PathId, user: CurrentUser, provider: Provider) -> None:
    await provider.delete_partner_meeting().execute(PartnerMeetingId(meeting_id), _actor(user))
