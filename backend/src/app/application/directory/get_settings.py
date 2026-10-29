from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.directory.credentials import try_unseal
from app.domain.common.errors import NotFoundError

if TYPE_CHECKING:
    from app.application.ports.secret_cipher import SecretCipher
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import StoredDirectorySettings


@dataclass(frozen=True, slots=True)
class DirectorySettingsView:
    """저장된 설정과 바인드 비밀번호를 읽을 수 있는지(비밀번호 자체는 담지 않는다)."""

    stored: StoredDirectorySettings
    credential_readable: bool


class GetDirectorySettings:
    """저장된 AD 설정을 돌려준다. 없으면 NotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, cipher: SecretCipher) -> None:
        self._uow_factory = uow_factory
        self._cipher = cipher

    async def execute(self) -> DirectorySettingsView:
        async with self._uow_factory() as uow:
            stored = await uow.directory_settings.get()
        if stored is None:
            raise NotFoundError("AD 설정", "directory")
        return DirectorySettingsView(stored, try_unseal(self._cipher, stored) is not None)
