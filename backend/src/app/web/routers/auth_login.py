"""AD 아이디·비밀번호 로그인. 성공하면 HttpOnly 세션 쿠키를 준다."""

from fastapi import APIRouter, Depends, Request, Response

from app.web.dependencies import Provider
from app.web.request_info import client_ip
from app.web.routers.responses import PROBLEM
from app.web.schemas.auth import LoginRequest, LoginResponse
from app.web.security import AUTH_PATH, Options, require_csrf_header, set_session_cookie

router = APIRouter(prefix=AUTH_PATH, tags=["auth"])


@router.post(
    "/login",
    dependencies=[Depends(require_csrf_header)],
    responses={401: PROBLEM, 409: PROBLEM, 422: PROBLEM, 429: PROBLEM, 503: PROBLEM},
)
async def login(
    body: LoginRequest, request: Request, response: Response, provider: Provider, options: Options
) -> LoginResponse:
    outcome = await provider.directory_login().execute(
        login_id=body.login_id, password=body.to_password(), client_ip=client_ip(request)
    )
    set_session_cookie(response, outcome.session.token, options)
    return LoginResponse.from_outcome(outcome)
