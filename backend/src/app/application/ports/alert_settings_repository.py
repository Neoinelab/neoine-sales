from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.alert.settings import StoredAlertSettings
    from app.domain.alert.thresholds import AlertThresholds
    from app.domain.user.value_objects import UserId


class AlertSettingsRepository(Protocol):
    async def get(self) -> StoredAlertSettings | None: ...

    async def save(
        self, thresholds: AlertThresholds, *, updated_by: UserId, now: datetime
    ) -> StoredAlertSettings:
        """단일 행 upsert. 마지막 저장이 이긴다."""
        ...
