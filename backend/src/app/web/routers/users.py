"""사용자 관리(admin 전용): 목록·등록·삭제. 비밀번호는 다루지 않는다."""

from uuid import UUID

from fastapi import Response, status

from app.domain.user.value_objects import UserId
from app.web.dependencies import DEFAULT_LIMIT, Limit, Offset, Provider
from app.web.permissions import admin_router
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.user import UserPage, UserRequest, UserResponse
from app.web.security import CurrentUser

router = admin_router(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=UserPage, responses={422: READ_ERRORS[422]})
async def list_users(
    provider: Provider, offset: Offset = 0, limit: Limit = DEFAULT_LIMIT
) -> UserPage:
    users = await provider.list_users().execute(offset=offset, limit=limit)
    return UserPage(
        items=[UserResponse.from_entity(user) for user in users], offset=offset, limit=limit
    )


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=UserResponse, responses=WRITE_ERRORS
)
async def register_user(
    body: UserRequest, response: Response, provider: Provider, actor: CurrentUser
) -> UserResponse:
    user = await provider.register_user().execute(
        login_id=body.login_id, role=body.role, actor=actor
    )
    response.headers["Location"] = f"{router.prefix}/{user.id}"
    return UserResponse.from_entity(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=WRITE_ERRORS)
async def delete_user(user_id: UUID, provider: Provider, actor: CurrentUser) -> Response:
    await provider.delete_user().execute(user_id=UserId(user_id), actor=actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
