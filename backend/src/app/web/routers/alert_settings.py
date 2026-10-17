"""경고 기준: 조회는 로그인한 모든 역할, 변경은 admin만."""

from fastapi import APIRouter, Depends

from app.web.dependencies import Provider
from app.web.permissions import require_admin
from app.web.routers.responses import PROBLEM
from app.web.schemas.alert_settings import (
    AlertSettingsRequest,
    AlertSettingsResponse,
    alert_settings_response,
)
from app.web.security import CurrentUser

router = APIRouter(prefix="/api/v1/alert-settings", tags=["settings"])


@router.get("", response_model=AlertSettingsResponse)
async def get_alert_settings(provider: Provider) -> AlertSettingsResponse:
    view = await provider.get_alert_settings().execute()
    return alert_settings_response(view)


@router.put(
    "",
    response_model=AlertSettingsResponse,
    dependencies=[Depends(require_admin)],
    responses={403: PROBLEM, 422: PROBLEM},
)
async def update_alert_settings(
    body: AlertSettingsRequest, provider: Provider, actor: CurrentUser
) -> AlertSettingsResponse:
    view = await provider.update_alert_settings().execute(actor=actor, stale_days=body.stale_days)
    return alert_settings_response(view)
