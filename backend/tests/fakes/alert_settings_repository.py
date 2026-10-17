"""AlertSettingsRepository Port의 InMemory 구현(Fake). 단일 행(id=1), 마지막 저장이 이긴다."""

from typing import TYPE_CHECKING

from app.domain.alert.settings import StoredAlertSettings

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.alert.thresholds import AlertThresholds
    from app.domain.user.value_objects import UserId

_ROW = 1


class FakeAlertSettingsRepository:
    def __init__(self) -> None:
        self._items: dict[int, StoredAlertSettings] = {}

    async def get(self) -> StoredAlertSettings | None:
        return self._items.get(_ROW)

    async def save(
        self, thresholds: AlertThresholds, *, updated_by: UserId, now: datetime
    ) -> StoredAlertSettings:
        stored = StoredAlertSettings(thresholds=thresholds, updated_at=now, updated_by=updated_by)
        self._items[_ROW] = stored  # 값 객체(frozen)라 복사가 필요 없다
        return stored
