from typing import TYPE_CHECKING

from app.domain.common.errors import NotFoundError
from app.domain.directory.errors import DirectorySettingsConflictError

if TYPE_CHECKING:
    from app.application.directory.verify_settings import VerifyDirectorySettings
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.credentials import Password
    from app.domain.auth.principal import Principal
    from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings


class UpdateDirectorySettings:
    """AD 설정을 저장한다. 새 설정으로 요청 admin이 인증에 성공해야 하며, 기존 세션은 유지한다."""

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, verify: VerifyDirectorySettings
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._verify = verify

    async def execute(
        self,
        *,
        actor: Principal,
        settings: DirectorySettings,
        expected_revision: int,
        password: Password | None,
        client_ip: str,
    ) -> StoredDirectorySettings:
        await self._ensure_current(expected_revision)
        await self._verify.execute(
            actor=actor, settings=settings, password=password, client_ip=client_ip
        )
        async with self._uow_factory() as uow:
            stored = await uow.directory_settings.save(
                settings,
                expected_revision=expected_revision,
                updated_by=actor.user_id,
                now=self._clock.now(),
            )
            await uow.commit()
        return stored

    async def _ensure_current(self, expected_revision: int) -> None:
        """AD에 묻기 전에 낡은 revision을 걸러낸다(저장 시점에 한 번 더 검사된다)."""
        async with self._uow_factory() as uow:
            current = await uow.directory_settings.get()
        if current is None:
            raise NotFoundError("AD 설정", "directory")
        if current.revision != expected_revision:
            raise DirectorySettingsConflictError
