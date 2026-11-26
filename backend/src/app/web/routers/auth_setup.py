"""최초 설정(admin이 생기면 닫힌다): 인증 방식 → (AD 서버) → 저장 위치 → 첫 admin. 세션 없음."""

from typing import Any, NoReturn

from fastapi import APIRouter, Depends, Request, Response

from app.domain.auth.mode import AuthMode
from app.web.dependencies import Provider
from app.web.request_info import client_ip
from app.web.routers.responses import PROBLEM
from app.web.schemas.auth import AuthModeRequest, PrincipalResponse, SetupAdminRequest
from app.web.schemas.auth_directory import (
    DirectorySettingsRequest,
    DirectorySettingsResponse,
    DirectorySettingsSaveRequest,
    directory_response,
)
from app.web.schemas.password_field import to_new_password
from app.web.schemas.settings_directory import DirectoryTestResultResponse
from app.web.schemas.storage import (
    StorageSettingsRequest,
    StorageSettingsResponse,
    storage_response,
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


@router.put("/setup/auth-mode", status_code=204, responses={409: PROBLEM, 422: PROBLEM})
async def setup_auth_mode(body: AuthModeRequest, provider: Provider) -> Response:
    await provider.choose_setup_auth_mode().execute(body.mode)
    return Response(status_code=204)


@router.put("/setup/directory", responses={409: PROBLEM, 422: PROBLEM})
async def setup_directory(
    body: DirectorySettingsSaveRequest, provider: Provider
) -> DirectorySettingsResponse:
    stored = await provider.register_setup_directory().execute(body.to_draft())
    return await directory_response(provider, stored)


@router.post("/setup/directory/test", responses={409: PROBLEM, 422: PROBLEM})
async def test_setup_directory(
    body: DirectorySettingsRequest, provider: Provider
) -> DirectoryTestResultResponse:
    result = await provider.test_setup_directory().execute(body.to_domain())
    return DirectoryTestResultResponse.from_result(result)


@router.put("/setup/storage", responses={409: PROBLEM, 422: PROBLEM})
async def setup_storage(
    body: StorageSettingsRequest, provider: Provider
) -> StorageSettingsResponse:
    stored = await provider.register_setup_storage().execute(body.path)
    return await storage_response(provider, stored)


@router.post("/setup/storage/test", status_code=204, responses={409: PROBLEM, 422: PROBLEM})
async def test_setup_storage(body: StorageSettingsRequest, provider: Provider) -> Response:
    await provider.test_setup_storage().execute(body.path)
    return Response(status_code=204)


async def _invalid_password(body: SetupAdminRequest, provider: Provider) -> NoReturn:
    """빈 비밀번호: local은 사용자 등록처럼 password 필드 422, AD는 기존대로 로그인 실패 401."""
    status = await provider.auth_status().execute()
    if status.auth_mode is AuthMode.LOCAL:
        to_new_password(body.password, "password")
    body.to_password()
    raise AssertionError("unreachable")  # pragma: no cover


@router.post("/setup", responses=SETUP_ERRORS)
async def setup_admin(
    body: SetupAdminRequest,
    request: Request,
    response: Response,
    provider: Provider,
    options: Options,
) -> PrincipalResponse:
    password = body.password_or_none() or await _invalid_password(body, provider)
    issued = await provider.setup_admin().execute(
        login_id=body.login_id,
        password=password,
        client_ip=client_ip(request),
        display_name=body.display_name,
        email=body.email,
        phone=body.phone,
    )
    set_session_cookie(response, issued.token, options)
    return PrincipalResponse.from_principal(issued.principal)
