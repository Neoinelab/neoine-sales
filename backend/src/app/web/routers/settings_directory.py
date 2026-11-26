"""AD 설정 관리: 테스트 계정은 요청 중에만 쓰고 저장은 성공 증명으로 검증한다."""

from typing import Any

from app.web.dependencies import Provider
from app.web.permissions import admin_router
from app.web.routers.responses import PROBLEM, READ_ERRORS
from app.web.schemas.auth_directory import DirectorySettingsResponse, directory_response
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
    stored = await provider.get_directory_settings().execute()
    return await directory_response(provider, stored)


@router.put("", response_model=DirectorySettingsResponse, responses=CHANGE_ERRORS)
async def update_directory_settings(
    body: DirectorySettingsUpdateRequest, provider: Provider, actor: CurrentUser
) -> DirectorySettingsResponse:
    stored = await provider.update_directory_settings().execute(
        actor=actor,
        draft=body.to_draft(),
        expected_revision=body.expected_revision,
    )
    return await directory_response(provider, stored)


@router.post("/test", response_model=DirectoryTestResultResponse, responses=CHANGE_ERRORS)
async def test_directory_settings(
    body: DirectorySettingsTestRequest, provider: Provider, actor: CurrentUser
) -> DirectoryTestResultResponse:
    result = await provider.test_directory_settings().execute(
        actor=actor,
        settings=body.to_domain(),
    )
    return DirectoryTestResultResponse.from_result(result)
