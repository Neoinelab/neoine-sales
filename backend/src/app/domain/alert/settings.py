from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.alert.thresholds import AlertThresholds
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class StoredAlertSettings:
    """저장된 경고 기준(단일 행)."""

    thresholds: AlertThresholds
    updated_at: datetime
    updated_by: UserId
