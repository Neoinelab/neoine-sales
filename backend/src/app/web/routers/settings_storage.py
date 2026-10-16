"""파일 저장 위치 관리(admin 전용): 조회·변경·쓰기 확인."""

from fastapi import Response

from app.web.dependencies import Provider
from app.web.permissions import admin_router
from app.web.routers.responses import PROBLEM, READ_ERRORS
from app.web.schemas.storage import (
    StorageSettingsRequest,
    StorageSettingsResponse,
    storage_response,
)
from app.web.security import CurrentUser

router = admin_router(prefix="/api/v1/settings/storage", tags=["settings"])


@router.get("", response_model=StorageSettingsResponse, responses={404: READ_ERRORS[404]})
async def get_storage_settings(provider: Provider) -> StorageSettingsResponse:
    stored = await provider.get_storage_settings().execute()
    return await storage_response(provider, stored)


@router.put("", response_model=StorageSettingsResponse, responses={422: PROBLEM})
async def update_storage_settings(
    body: StorageSettingsRequest, provider: Provider, actor: CurrentUser
) -> StorageSettingsResponse:
    stored = await provider.update_storage_settings().execute(actor=actor, raw_path=body.path)
    return await storage_response(provider, stored)


@router.post("/test", status_code=204, responses={422: PROBLEM})
async def test_storage_settings(body: StorageSettingsRequest, provider: Provider) -> Response:
    await provider.test_storage_settings().execute(body.path)
    return Response(status_code=204)
