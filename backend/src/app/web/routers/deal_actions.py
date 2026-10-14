"""Deal 활동 이력. 등록·Deal별 조회는 Deal 아래에, 개별 조작과 전체 검색은 /deal-actions에 둔다."""

from typing import Annotated
from uuid import UUID

from fastapi import Query, Response, status

from app.domain.deal.value_objects import DealId
from app.domain.deal_action.value_objects import DealActionId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.deal_action import (
    DealActionPage,
    DealActionRequest,
    DealActionResponse,
    DealActionSearchParams,
    GlobalDealActionSearchParams,
    action_response,
    action_responses,
)

router = BusinessRouter(prefix="/api/v1", tags=["deal-actions"])
Search = Annotated[DealActionSearchParams, Query()]
GlobalSearch = Annotated[GlobalDealActionSearchParams, Query()]


async def _search(
    provider: Provider, params: DealActionSearchParams, deal_id: UUID | None
) -> DealActionPage:
    query = params.to_query(deal_id)
    found = await provider.search_deal_actions().execute(query)
    items = await action_responses(provider, found)
    return DealActionPage(items=items, offset=query.offset, limit=query.limit)


@router.post(
    "/deals/{deal_id}/actions",
    status_code=status.HTTP_201_CREATED,
    response_model=DealActionResponse,
    responses=WRITE_ERRORS,
)
async def register_deal_action(
    deal_id: UUID, body: DealActionRequest, response: Response, provider: Provider
) -> DealActionResponse:
    action = await provider.register_deal_action().execute(DealId(deal_id), body.to_input())
    response.headers["Location"] = f"{router.prefix}/deal-actions/{action.id}"
    return await action_response(provider, action)


@router.get("/deals/{deal_id}/actions", response_model=DealActionPage, responses=READ_ERRORS)
async def list_actions_of_deal(deal_id: UUID, params: Search, provider: Provider) -> DealActionPage:
    return await _search(provider, params, deal_id)


@router.get("/deal-actions", response_model=DealActionPage, responses=READ_ERRORS)
async def search_deal_actions(params: GlobalSearch, provider: Provider) -> DealActionPage:
    return await _search(provider, params, None)


@router.get("/deal-actions/{action_id}", response_model=DealActionResponse, responses=READ_ERRORS)
async def get_deal_action(action_id: UUID, provider: Provider) -> DealActionResponse:
    action = await provider.get_deal_action().execute(DealActionId(action_id))
    return await action_response(provider, action)


@router.put("/deal-actions/{action_id}", response_model=DealActionResponse, responses=WRITE_ERRORS)
async def update_deal_action(
    action_id: UUID, body: DealActionRequest, provider: Provider
) -> DealActionResponse:
    action = await provider.update_deal_action().execute(DealActionId(action_id), body.to_input())
    return await action_response(provider, action)


@router.delete(
    "/deal-actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT, responses=READ_ERRORS
)
async def delete_deal_action(action_id: UUID, provider: Provider) -> None:
    await provider.delete_deal_action().execute(DealActionId(action_id))
