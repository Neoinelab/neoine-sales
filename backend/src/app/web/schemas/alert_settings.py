"""경고 기준 스키마(P3). 범위 판단은 도메인이 하고 스키마는 정수 형식만 본다."""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, StrictInt

from app.web.schemas.common import RequestModel
from app.web.schemas.user_ref import UserRef

if TYPE_CHECKING:
    from app.application.alert.views import AlertSettingsView


class AlertSettingsRequest(RequestModel):
    stale_days: StrictInt


class AlertSettingsResponse(BaseModel):
    stale_days: int
    updated_at: datetime | None
    updated_by: UserRef | None


def alert_settings_response(view: AlertSettingsView) -> AlertSettingsResponse:
    """저장자는 view가 이미 표시 이름을 갖고 있다. 저장 전이면 updated_at·updated_by는 None."""
    saver = view.updated_by
    return AlertSettingsResponse(
        stale_days=view.thresholds.stale_days,
        updated_at=view.updated_at,
        updated_by=None if saver is None else UserRef.from_domain(saver),
    )
