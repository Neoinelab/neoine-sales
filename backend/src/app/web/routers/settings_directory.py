"""AD 설정 관리(admin 전용): 조회·저장·연결 테스트. 저장·테스트는 admin 비밀번호로 검증."""

from typing import Any

from fastapi import Request

from app.web.dependencies import Provider
from app.web.permissions import admin_router
from app.web.request_info import client_ip
from app.web.routers.responses import PROBLEM, READ_ERRORS
from app.web.schemas.auth_directory import DirectorySettingsResponse
from app.web.schemas.settings_directory import (
    DirectorySettingsTestRequest,
    DirectorySettingsUpdateRequest,
    DirectoryTestResultResponse,
)
from app.web.security import CurrentUser

router = admin_router(prefix="/api/v1/settings/directory", tags=["settings"])
CHANGE_ERRORS: dict[int | str, dict[str, Any]] = {
    404: PROBLEM,
    409: PROBLEM,
    422: PROBLEM,
    429: PROBLEM,
}


@router.get("", response_model=DirectorySettingsResponse, responses={404: READ_ERRORS[404]})
async def get_directory_settings(provider: Provider) -> DirectorySettingsResponse:
    return DirectorySettingsResponse.from_stored(await provider.get_directory_settings().execute())


@router.put("", response_model=DirectorySettingsResponse, responses=CHANGE_ERRORS)
async def update_directory_settings(
    body: DirectorySettingsUpdateRequest, request: Request, provider: Provider, actor: CurrentUser
) -> DirectorySettingsResponse:
    stored = await provider.update_directory_settings().execute(
        actor=actor,
        settings=body.to_domain(),
        expected_revision=body.expected_revision,
        password=body.to_password(),
        client_ip=client_ip(request),
    )
    return DirectorySettingsResponse.from_stored(stored)


@router.post("/test", response_model=DirectoryTestResultResponse, responses=CHANGE_ERRORS)
async def test_directory_settings(
    body: DirectorySettingsTestRequest, request: Request, provider: Provider, actor: CurrentUser
) -> DirectoryTestResultResponse:
    result = await provider.test_directory_settings().execute(
        actor=actor,
        settings=body.to_domain(),
        password=body.to_password(),
        client_ip=client_ip(request),
    )
    return DirectoryTestResultResponse.from_result(result)
