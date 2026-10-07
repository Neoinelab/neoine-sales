"""로그인·로그아웃. 백엔드가 OIDC 흐름을 맡고 브라우저에는 HttpOnly 세션 쿠키만 준다."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.application.auth.issue_session import IssuedSession
from app.domain.auth.errors import AccessDeniedError, AuthenticationError
from app.web.dependencies import Provider
from app.web.routers.responses import PROBLEM
from app.web.schemas.auth import (
    AuthConfigResponse,
    CallbackQuery,
    DevLoginRequest,
    PrincipalResponse,
)
from app.web.security import (
    AUTH_PATH,
    LOGIN_COOKIE,
    SESSION_COOKIE,
    AuthOptions,
    CurrentUser,
    Options,
    require_csrf_header,
)

router = APIRouter(prefix=AUTH_PATH, tags=["auth"])
LOGIN_COOKIE_SECONDS = 600
HOME = "/"


def _set_session_cookie(response: Response, issued: IssuedSession, options: AuthOptions) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        issued.token,
        max_age=options.session_ttl_seconds,
        httponly=True,
        secure=options.cookie_secure,
        samesite="lax",
        path="/",
    )


def _login_error(code: str, options: AuthOptions) -> RedirectResponse:
    response = RedirectResponse(f"/login?error={code}", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(LOGIN_COOKIE, path=AUTH_PATH, secure=options.cookie_secure)
    return response


def _require(enabled: bool) -> None:
    if not enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용할 수 없는 기능입니다")


@router.get("/config")
async def auth_config(options: Options) -> AuthConfigResponse:
    return AuthConfigResponse(dev_login=options.dev_login_enabled, oidc=options.oidc_enabled)


@router.get("/login", status_code=status.HTTP_302_FOUND, response_class=RedirectResponse)
async def login(provider: Provider, options: Options) -> RedirectResponse:
    _require(options.oidc_enabled)
    start = await provider.begin_login().execute()
    response = RedirectResponse(start.redirect_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        LOGIN_COOKIE,
        start.pending_token,
        max_age=LOGIN_COOKIE_SECONDS,
        httponly=True,
        secure=options.cookie_secure,
        samesite="lax",
        path=AUTH_PATH,
    )
    return response


@router.get("/callback", status_code=status.HTTP_302_FOUND, response_class=RedirectResponse)
async def callback(
    query: Annotated[CallbackQuery, Query()],
    provider: Provider,
    options: Options,
    login_cookie: Annotated[str | None, Cookie(alias=LOGIN_COOKIE)] = None,
) -> RedirectResponse:
    _require(options.oidc_enabled)
    if query.error or not query.code or not query.state:
        return _login_error("auth", options)
    try:
        issued = await provider.complete_login().execute(
            code=query.code, state=query.state, pending_token=login_cookie
        )
    except AccessDeniedError:
        return _login_error("denied", options)
    except AuthenticationError:
        return _login_error("auth", options)
    response = RedirectResponse(HOME, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(LOGIN_COOKIE, path=AUTH_PATH, secure=options.cookie_secure)
    _set_session_cookie(response, issued, options)
    return response


@router.post("/dev-login", dependencies=[Depends(require_csrf_header)])
async def dev_login(
    body: DevLoginRequest, response: Response, provider: Provider, options: Options
) -> PrincipalResponse:
    _require(options.dev_login_enabled)
    issued = await provider.dev_login().execute(body.role)
    _set_session_cookie(response, issued, options)
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
