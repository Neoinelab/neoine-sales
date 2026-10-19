"""Action 유형. 조회는 로그인 사용자, 생성은 sales·admin, 이름 변경·삭제는 admin 전용."""

from uuid import UUID

from fastapi import Depends, Response, status

from app.domain.action_type.values import ActionTypeId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter, require_admin
from app.web.routers.responses import PROBLEM, READ_ERRORS, WRITE_ERRORS
from app.web.schemas.action_type import (
    ActionTypeNameRequest,
    ActionTypeResponse,
    action_type_responses,
)
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/action-types", tags=["action-types"])
ADMIN = [Depends(require_admin)]


@router.get("", response_model=list[ActionTypeResponse])
async def list_action_types(provider: Provider) -> list[ActionTypeResponse]:
    return await action_type_responses(provider, await provider.list_action_types().execute())


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ActionTypeResponse,
    responses=WRITE_ERRORS,
)
async def create_action_type(
    body: ActionTypeNameRequest, response: Response, user: CurrentUser, provider: Provider
) -> ActionTypeResponse:
    item = await provider.register_action_type().execute(body.name, user.user_id)
    response.headers["Location"] = f"{router.prefix}/{item.action_type.id}"
    (result,) = await action_type_responses(provider, [item])
    return result


@router.patch(
    "/{type_id}", response_model=ActionTypeResponse, dependencies=ADMIN, responses=WRITE_ERRORS
)
async def rename_action_type(
    type_id: UUID, body: ActionTypeNameRequest, provider: Provider
) -> ActionTypeResponse:
    item = await provider.rename_action_type().execute(ActionTypeId(type_id), body.name)
    (result,) = await action_type_responses(provider, [item])
    return result


@router.delete(
    "/{type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=ADMIN,
    responses={**READ_ERRORS, 409: PROBLEM},
)
async def delete_action_type(type_id: UUID, provider: Provider) -> None:
    await provider.delete_action_type().execute(ActionTypeId(type_id))
