from typing import TYPE_CHECKING

from app.application.auth.mode import ensure_directory_mode
from app.application.ports.directory_settings_repository import DirectorySettingsWrite
from app.domain.common.errors import NotFoundError
from app.domain.directory.errors import DirectorySettingsConflictError

if TYPE_CHECKING:
    from app.application.directory.connection_proof import DirectoryConnectionProof
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.directory.settings import DirectorySettingsDraft, StoredDirectorySettings


class UpdateDirectorySettings:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, proof: DirectoryConnectionProof
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._proof = proof

    async def execute(
        self, *, actor: Principal, draft: DirectorySettingsDraft, expected_revision: int | None
    ) -> StoredDirectorySettings:
        async with self._uow_factory() as uow:
            await ensure_directory_mode(uow)
            current = await uow.directory_settings.get()
        if expected_revision is None:
            if current is not None:
                raise DirectorySettingsConflictError
        elif current is None:
            raise NotFoundError("AD 설정", "directory")
        elif current.revision != expected_revision:
            raise DirectorySettingsConflictError
        base_dn = self._proof.verify(draft.connection, draft.test_token, f"admin:{actor.user_id}")
        async with self._uow_factory() as uow:
            await ensure_directory_mode(uow)
            stored = await uow.directory_settings.save(
                DirectorySettingsWrite(
                    connection=draft.connection,
                    base_dn=base_dn,
                    expected_revision=expected_revision,
                    updated_by=actor.user_id,
                    now=self._clock.now(),
                )
            )
            await uow.commit()
        return stored
