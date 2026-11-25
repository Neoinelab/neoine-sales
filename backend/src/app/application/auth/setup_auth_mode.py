from typing import TYPE_CHECKING

from app.application.auth.mode import ensure_setup_open

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.mode import AuthMode, AuthSettings


class ChooseSetupAuthMode:
    """설정이 열려 있는 동안 인증 방식(AD 연동/직접 관리)을 고른다(덮어쓰기).

    저장된 AD 설정은 지우지 않는다(local이면 쓰이지 않는다).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, mode: AuthMode) -> AuthSettings:
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            await ensure_setup_open(uow)
            saved = await uow.auth_settings.save(mode, now=self._clock.now(), setup_pending=True)
            await uow.commit()
        return saved
