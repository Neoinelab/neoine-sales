from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.alert.thresholds import AlertThresholds
    from app.domain.user.value_objects import UserRef


@dataclass(frozen=True, slots=True)
class AlertSettingsView:
    """저장 기록이 없으면 기본값이고 updated_at·updated_by는 None."""

    thresholds: AlertThresholds
    updated_at: datetime | None
    updated_by: UserRef | None
