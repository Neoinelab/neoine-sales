from typing import TYPE_CHECKING

from app.application.auth.messages import SETUP_CLOSED
from app.application.directory.errors import DirectoryVerificationError
from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.common.errors import InvalidStateError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.directory import DirectoryAuthenticator
    from app.application.ports.secret_cipher import SecretCipher
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings


class RegisterSetupDirectory:
    """최초 설정 1단계: admin이 생기기 전까지 AD 서버 설정을 등록(덮어쓰기)한다.

    서비스 계정으로 바인드해 Base DN을 찾는 데까지만 확인하고, 비밀번호는 암호화해 저장한다.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        directory: DirectoryAuthenticator,
        cipher: SecretCipher,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._directory = directory
        self._cipher = cipher

    async def execute(self, settings: DirectorySettings) -> StoredDirectorySettings:
        async with self._uow_factory() as uow:
            await self._ensure_open(uow)
        base_dn = await self._discover(settings)
        sealed = self._cipher.seal(settings.bind_password.reveal())
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            await self._ensure_open(uow)
            current = await uow.directory_settings.get()
            stored = await uow.directory_settings.save(
                settings.connection,
                sealed,
                base_dn,
                expected_revision=None if current is None else current.revision,
                updated_by=None,
                now=self._clock.now(),
            )
            await uow.commit()
        return stored

    @staticmethod
    async def _ensure_open(uow: UnitOfWork) -> None:
        if await uow.users.count_active_admins() > 0:
            raise InvalidStateError(SETUP_CLOSED)

    async def _discover(self, settings: DirectorySettings) -> str:
        try:
            return await self._directory.discover_base_dn(settings)
        except DirectoryUnavailableError as error:
            # 원인 문구는 서버 내부 정보를 담을 수 있어 단계만 옮긴다
            raise DirectoryVerificationError(error.stage or VerificationStage.CONNECT) from None
