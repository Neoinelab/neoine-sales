from typing import TYPE_CHECKING

from app.application.alert.views import AlertSettingsView
from app.domain.alert.thresholds import AlertThresholds

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal


class UpdateAlertSettings:
    """admin이 경고 기준을 바꾼다. 검증을 통과해야 저장한다(admin 판정은 web 의존성)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, *, actor: Principal, stale_days: int) -> AlertSettingsView:
        thresholds = AlertThresholds(stale_days=stale_days)
        async with self._uow_factory() as uow:
            stored = await uow.alert_settings.save(
                thresholds, updated_by=actor.user_id, now=self._clock.now()
            )
            refs = await uow.users.get_refs([actor.user_id])
            await uow.commit()
        return AlertSettingsView(stored.thresholds, stored.updated_at, refs.get(stored.updated_by))
