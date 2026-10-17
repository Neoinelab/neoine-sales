from typing import TYPE_CHECKING

from app.application.alert.views import AlertSettingsView
from app.domain.alert.thresholds import AlertThresholds

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class GetAlertSettings:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> AlertSettingsView:
        async with self._uow_factory() as uow:
            stored = await uow.alert_settings.get()
            if stored is None:
                return AlertSettingsView(AlertThresholds.default(), None, None)
            refs = await uow.users.get_refs([stored.updated_by])
        return AlertSettingsView(stored.thresholds, stored.updated_at, refs.get(stored.updated_by))
