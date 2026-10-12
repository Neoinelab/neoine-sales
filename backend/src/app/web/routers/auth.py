"""설정 조회·세션 확인·로그아웃·개발용 로그인. 로그인(AD)은 auth_login, 최초 설정은 auth_setup."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.web.dependencies import Provider
from app.web.routers.responses import PROBLEM
from app.web.schemas.auth import AuthConfigResponse, DevLoginRequest, PrincipalResponse
from app.web.security import (
    AUTH_PATH,
    SESSION_COOKIE,
    CurrentUser,
    Options,
    require_csrf_header,
    set_session_cookie,
)

router = APIRouter(prefix=AUTH_PATH, tags=["auth"])


@router.get("/config")
async def auth_config(provider: Provider, options: Options) -> AuthConfigResponse:
    auth_status = await provider.auth_status().execute()
    return AuthConfigResponse.from_status(auth_status, dev_login=options.dev_login_enabled)


@router.post("/dev-login", dependencies=[Depends(require_csrf_header)])
async def dev_login(
    body: DevLoginRequest, response: Response, provider: Provider, options: Options
) -> PrincipalResponse:
    if not options.dev_login_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용할 수 없는 기능입니다")
    issued = await provider.dev_login().execute(body.role)
    set_session_cookie(response, issued.token, options)
    return PrincipalResponse.from_principal(issued.principal)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
async def logout(request: Request, provider: Provider, options: Options) -> Response:
    await provider.logout().execute(request.cookies.get(SESSION_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=options.cookie_secure)
    return response


@router.get("/me", responses={401: PROBLEM})
async def me(user: CurrentUser) -> PrincipalResponse:
    return PrincipalResponse.from_principal(user)
