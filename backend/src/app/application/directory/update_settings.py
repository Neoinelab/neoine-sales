from typing import TYPE_CHECKING

from app.application.directory.credentials import resolve_draft
from app.domain.common.errors import NotFoundError
from app.domain.directory.errors import DirectorySettingsConflictError

if TYPE_CHECKING:
    from app.application.directory.verify_settings import VerifyDirectorySettings
    from app.application.ports.clock import Clock
    from app.application.ports.secret_cipher import SecretCipher
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.credentials import Password
    from app.domain.auth.principal import Principal
    from app.domain.directory.settings import DirectorySettingsDraft, StoredDirectorySettings


class UpdateDirectorySettings:
    """AD 설정을 저장한다. 새 설정으로 요청 admin이 인증에 성공해야 하며, 기존 세션은 유지한다.

    expected_revision이 None이면 설정이 아직 없을 때 새로 만든다.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        cipher: SecretCipher,
        verify: VerifyDirectorySettings,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._cipher = cipher
        self._verify = verify

    async def execute(
        self,
        *,
        actor: Principal,
        draft: DirectorySettingsDraft,
        expected_revision: int | None,
        password: Password | None,
        client_ip: str,
    ) -> StoredDirectorySettings:
        current = await self._current(expected_revision)
        settings = resolve_draft(draft, current, self._cipher)
        base_dn = await self._verify.execute(
            actor=actor, settings=settings, password=password, client_ip=client_ip
        )
        sealed = self._cipher.seal(settings.bind_password.reveal())
        async with self._uow_factory() as uow:
            stored = await uow.directory_settings.save(
                settings.connection,
                sealed,
                base_dn,
                expected_revision=expected_revision,
                updated_by=actor.user_id,
                now=self._clock.now(),
            )
            await uow.commit()
        return stored

    async def _current(self, expected_revision: int | None) -> StoredDirectorySettings | None:
        """AD에 묻기 전에 낡은 revision을 걸러낸다(저장 시점에 한 번 더 검사된다)."""
        async with self._uow_factory() as uow:
            current = await uow.directory_settings.get()
        if expected_revision is None:
            if current is not None:
                raise DirectorySettingsConflictError
        elif current is None:
            raise NotFoundError("AD 설정", "directory")
        elif current.revision != expected_revision:
            raise DirectorySettingsConflictError
        return current
