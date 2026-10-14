"""최초 설정 2단계(admin이 생기면 닫힌다): AD 서버 등록 → 첫 admin 로그인. 세션 없이 호출한다."""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.web.dependencies import Provider
from app.web.request_info import client_ip
from app.web.routers.responses import PROBLEM
from app.web.schemas.auth import PrincipalResponse, SetupAdminRequest
from app.web.schemas.auth_directory import (
    DirectorySettingsRequest,
    DirectorySettingsResponse,
    directory_response,
)
from app.web.security import AUTH_PATH, Options, require_csrf_header, set_session_cookie

router = APIRouter(prefix=AUTH_PATH, tags=["auth"], dependencies=[Depends(require_csrf_header)])
SETUP_ERRORS: dict[int | str, dict[str, Any]] = {
    401: PROBLEM,
    409: PROBLEM,
    422: PROBLEM,
    429: PROBLEM,
    503: PROBLEM,
}


@router.put("/setup/directory", responses={409: PROBLEM, 422: PROBLEM})
async def setup_directory(
    body: DirectorySettingsRequest, provider: Provider
) -> DirectorySettingsResponse:
    stored = await provider.register_setup_directory().execute(body.to_domain())
    return await directory_response(provider, stored)


@router.post("/setup", responses=SETUP_ERRORS)
async def setup_admin(
    body: SetupAdminRequest,
    request: Request,
    response: Response,
    provider: Provider,
    options: Options,
) -> PrincipalResponse:
    issued = await provider.setup_first_admin().execute(
        login_id=body.login_id, password=body.to_password(), client_ip=client_ip(request)
    )
    set_session_cookie(response, issued.token, options)
    return PrincipalResponse.from_principal(issued.principal)
