"""내 정보: 프로필 조회·수정, 비밀번호 변경. 로그인한 모든 역할이 쓴다(읽기 전용 계정 포함)."""

from fastapi import APIRouter, Request, Response

from app.domain.auth.errors import WeakPasswordError
from app.web.dependencies import Provider
from app.web.request_info import client_ip
from app.web.routers.responses import PROBLEM
from app.web.schemas.me import MyPasswordRequest, MyProfileRequest, MyProfileResponse
from app.web.schemas.password_field import InvalidFieldError, to_new_password
from app.web.security import SESSION_COOKIE, CurrentUser

# 쓰기 차단(읽기 전용 role) 규칙을 쓰는 BusinessRouter가 아니라 일반 라우터라 role과 무관하다.
router = APIRouter(prefix="/api/v1/me", tags=["me"])


@router.get("/profile")
async def get_my_profile(provider: Provider, actor: CurrentUser) -> MyProfileResponse:
    return MyProfileResponse.from_profile(await provider.get_my_profile().execute(actor))


@router.patch("/profile", responses={409: PROBLEM, 422: PROBLEM})
async def update_my_profile(
    body: MyProfileRequest, provider: Provider, actor: CurrentUser
) -> MyProfileResponse:
    profile = await provider.update_my_profile().execute(actor=actor, changes=body.to_changes())
    return MyProfileResponse.from_profile(profile)


@router.put("/password", status_code=204, responses={409: PROBLEM, 422: PROBLEM, 429: PROBLEM})
async def change_my_password(
    body: MyPasswordRequest, request: Request, provider: Provider, actor: CurrentUser
) -> Response:
    try:
        await provider.change_my_password().execute(
            actor=actor,
            current=to_new_password(body.current_password, "current_password"),
            new=to_new_password(body.new_password, "new_password"),
            session_token=request.cookies.get(SESSION_COOKIE, ""),
            client_ip=client_ip(request),
        )
    except WeakPasswordError as error:
        raise InvalidFieldError(("new_password",), str(error)) from None
    return Response(status_code=204)
