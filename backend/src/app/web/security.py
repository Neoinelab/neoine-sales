"""세션 쿠키 인증과 CSRF 방어. 보호할 라우터에 의존성으로 붙인다."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.domain.auth.principal import Principal
from app.web.dependencies import Provider

SESSION_COOKIE = "neoine_session"
LOGIN_COOKIE = "neoine_login"
AUTH_PATH = "/api/v1/auth"
CSRF_HEADER = "x-requested-with"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True, slots=True)
class AuthOptions:
    cookie_secure: bool
    session_ttl_seconds: int
    oidc_enabled: bool
    dev_login_enabled: bool


class CsrfRejectedError(Exception):
    """상태를 바꾸는 요청에 CSRF 방어 헤더가 없다."""


def get_auth_options(request: Request) -> AuthOptions:
    options: AuthOptions = request.app.state.auth_options
    return options


async def require_login(request: Request, provider: Provider) -> Principal:
    principal = await provider.authenticate().execute(request.cookies.get(SESSION_COOKIE))
    request.state.principal = principal
    return principal


async def require_csrf_header(request: Request) -> None:
    """다른 출처는 CORS 허용 없이 커스텀 헤더를 못 보낸다. 쿠키 인증의 보완책이다."""
    if request.method not in SAFE_METHODS and not request.headers.get(CSRF_HEADER):
        raise CsrfRejectedError


CurrentUser = Annotated[Principal, Depends(require_login)]
Options = Annotated[AuthOptions, Depends(get_auth_options)]
