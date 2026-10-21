"""사용자 관리(admin 전용): 목록·등록·삭제(퇴사 처리). 비밀번호는 다루지 않는다."""

from typing import Annotated, Literal

from fastapi import Query, Response, status

from app.domain.user.entities import User
from app.domain.user.value_objects import UserDeleteReason, UserId, UserStatusFilter
from app.web.dependencies import DEFAULT_LIMIT, Limit, Offset, Provider
from app.web.permissions import admin_router
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.ids import PathId
from app.web.schemas.user import DeleteUserResponse, UserPage, UserRequest, UserResponse
from app.web.schemas.user_ref import resolve_refs
from app.web.security import CurrentUser

router = admin_router(prefix="/api/v1/users", tags=["users"])
# 값이 하나뿐인 Literal은 const로만 문서화되므로, 값 추가를 대비해 enum으로도 적는다
REASON_SCHEMA = {"enum": [reason.value for reason in UserDeleteReason]}


async def _responses(provider: Provider, users: list[User]) -> list[UserResponse]:
    refs = await resolve_refs(provider, [u.created_by_user_id for u in users])
    return [UserResponse.from_entity(user, refs) for user in users]


@router.get("", response_model=UserPage, responses={422: READ_ERRORS[422]})
async def list_users(
    provider: Provider,
    offset: Offset = 0,
    limit: Limit = DEFAULT_LIMIT,
    status: Literal["active", "resigned", "all"] = "active",
) -> UserPage:
    users = await provider.list_users().execute(
        status=UserStatusFilter(status), offset=offset, limit=limit
    )
    return UserPage(items=await _responses(provider, list(users)), offset=offset, limit=limit)


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=UserResponse, responses=WRITE_ERRORS
)
async def register_user(
    body: UserRequest, response: Response, provider: Provider, actor: CurrentUser
) -> UserResponse:
    user = await provider.register_user().execute(
        login_id=body.login_id,
        role=body.role,
        actor=actor,
        display_name=body.display_name,
    )
    response.headers["Location"] = f"{router.prefix}/{user.id}"
    (item,) = await _responses(provider, [user])
    return item


@router.delete("/{user_id}", response_model=DeleteUserResponse, responses=WRITE_ERRORS)
async def delete_user(
    user_id: PathId,
    provider: Provider,
    actor: CurrentUser,
    reason: Annotated[Literal["resigned"], Query(json_schema_extra=REASON_SCHEMA)] = "resigned",
) -> DeleteUserResponse:
    outcome = await provider.delete_user().execute(
        user_id=UserId(user_id), actor=actor, reason=UserDeleteReason(reason)
    )
    return DeleteUserResponse.from_outcome(outcome)
