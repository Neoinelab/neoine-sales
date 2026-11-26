from typing import TYPE_CHECKING

from app.application.auth.mode import ensure_setup_open
from app.application.ports.directory_settings_repository import DirectorySettingsWrite
from app.domain.auth.mode import AuthMode, SetupProgress

if TYPE_CHECKING:
    from app.application.directory.connection_proof import DirectoryConnectionProof
    from app.application.directory.result import TestResult
    from app.application.directory.verify_settings import VerifyDirectorySettings
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import (
        DirectorySettings,
        DirectorySettingsDraft,
        StoredDirectorySettings,
    )


class RegisterSetupDirectory:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, proof: DirectoryConnectionProof
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._proof = proof

    async def execute(self, draft: DirectorySettingsDraft) -> StoredDirectorySettings:
        async with self._uow_factory() as uow:
            await ensure_setup_open(uow)
        base_dn = self._proof.verify(draft.connection, draft.test_token, "setup")
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            await ensure_setup_open(uow)
            current = await uow.directory_settings.get()
            now = self._clock.now()
            stored = await uow.directory_settings.save(
                DirectorySettingsWrite(
                    connection=draft.connection,
                    base_dn=base_dn,
                    expected_revision=None if current is None else current.revision,
                    updated_by=None,
                    now=now,
                )
            )
            await uow.auth_settings.save(
                AuthMode.AD,
                now=now,
                progress=SetupProgress(storage_pending=True, admin_pending=True),
            )
            await uow.commit()
        return stored


class TestSetupDirectory:
    __test__ = False

    def __init__(self, uow_factory: UnitOfWorkFactory, verify: VerifyDirectorySettings) -> None:
        self._uow_factory = uow_factory
        self._verify = verify

    async def execute(self, settings: DirectorySettings) -> TestResult:
        async with self._uow_factory() as uow:
            await ensure_setup_open(uow)
        return await self._verify.execute(settings, "setup")
