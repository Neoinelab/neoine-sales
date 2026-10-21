"""Deal 활동 이력. 등록·Deal별 조회는 Deal 아래에, 개별 조작은 /deal-actions에 둔다."""

from typing import Annotated

from fastapi import Query, Response, status

from app.application.deal.inputs import Actor
from app.domain.deal_action.value_objects import DealActionId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import READ_ERRORS, STATUS_ERRORS, WRITE_ERRORS
from app.web.schemas.deal_action import (
    DealActionCreateRequest,
    DealActionList,
    DealActionResponse,
    DealActionSearchParams,
    DealActionUpdateRequest,
    NextActionStatusRequest,
    action_response,
    action_responses,
)
from app.web.schemas.ids import PathId
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1", tags=["deal-actions"])
Search = Annotated[DealActionSearchParams, Query()]


def _actor(user: CurrentUser) -> Actor:
    return Actor(user_id=user.user_id, role=user.role)


@router.post(
    "/deals/{code}/actions",
    status_code=status.HTTP_201_CREATED,
    response_model=DealActionResponse,
    responses=WRITE_ERRORS,
)
async def register_deal_action(
    code: str,
    body: DealActionCreateRequest,
    response: Response,
    user: CurrentUser,
    provider: Provider,
) -> DealActionResponse:
    action = await provider.register_deal_action().execute(code, body.to_input(), _actor(user))
    response.headers["Location"] = f"{router.prefix}/deal-actions/{action.id}"
    return await action_response(provider, action)


@router.get("/deals/{code}/actions", response_model=DealActionList, responses=READ_ERRORS)
async def list_actions_of_deal(code: str, params: Search, provider: Provider) -> DealActionList:
    found = await provider.list_deal_actions().execute(params.to_query(code))
    return DealActionList(items=await action_responses(provider, found))


@router.get("/deal-actions/{action_id}", response_model=DealActionResponse, responses=READ_ERRORS)
async def get_deal_action(action_id: PathId, provider: Provider) -> DealActionResponse:
    action = await provider.get_deal_action().execute(DealActionId(action_id))
    return await action_response(provider, action)


@router.put("/deal-actions/{action_id}", response_model=DealActionResponse, responses=WRITE_ERRORS)
async def update_deal_action(
    action_id: PathId, body: DealActionUpdateRequest, user: CurrentUser, provider: Provider
) -> DealActionResponse:
    action = await provider.update_deal_action().execute(
        DealActionId(action_id), body.to_input(), _actor(user)
    )
    return await action_response(provider, action)


@router.delete(
    "/deal-actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT, responses=READ_ERRORS
)
async def delete_deal_action(action_id: PathId, user: CurrentUser, provider: Provider) -> None:
    await provider.delete_deal_action().execute(DealActionId(action_id), _actor(user))


@router.put(
    "/deal-actions/{action_id}/next-action-status",
    response_model=DealActionResponse,
    responses=STATUS_ERRORS,
)
async def change_next_action_status(
    action_id: PathId, body: NextActionStatusRequest, user: CurrentUser, provider: Provider
) -> DealActionResponse:
    action = await provider.change_next_action_status().execute(
        DealActionId(action_id), body.to_input(), _actor(user)
    )
    return await action_response(provider, action)
