from typing import TYPE_CHECKING

from app.application.auth.mode import ensure_setup_open
from app.application.directory.errors import DirectoryVerificationError
from app.application.directory.test_settings import SUCCESS_MESSAGE, TestResult
from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.mode import AuthMode, SetupProgress

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.directory import DirectoryAuthenticator
    from app.application.ports.secret_cipher import SecretCipher
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import DirectorySettings, StoredDirectorySettings


class RegisterSetupDirectory:
    """설정이 열려 있는 동안 AD 서버 설정을 등록(덮어쓰기)한다.

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
            await ensure_setup_open(uow)
        base_dn = await discover_setup_base_dn(self._directory, settings)
        sealed = self._cipher.seal(settings.bind_password.reveal())
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            await ensure_setup_open(uow)
            current = await uow.directory_settings.get()
            now = self._clock.now()
            stored = await uow.directory_settings.save(
                settings.connection,
                sealed,
                base_dn,
                expected_revision=None if current is None else current.revision,
                updated_by=None,
                now=now,
            )
            await uow.auth_settings.save(
                AuthMode.AD,
                now=now,
                progress=SetupProgress(storage_pending=True, admin_pending=True),
            )
            await uow.commit()
        return stored


class TestSetupDirectory:
    """최초 설정 AD 연결 테스트. 서비스 계정 바인드·Base DN 탐색까지만 하고 저장하지 않는다."""

    __test__ = False

    def __init__(self, uow_factory: UnitOfWorkFactory, directory: DirectoryAuthenticator) -> None:
        self._uow_factory = uow_factory
        self._directory = directory

    async def execute(self, settings: DirectorySettings) -> TestResult:
        async with self._uow_factory() as uow:
            await ensure_setup_open(uow)
        try:
            base_dn = await discover_setup_base_dn(self._directory, settings)
        except DirectoryVerificationError as error:
            return TestResult(success=False, stage=error.stage, message=error.message)
        return TestResult(success=True, stage=None, message=SUCCESS_MESSAGE, base_dn=base_dn)


async def discover_setup_base_dn(
    directory: DirectoryAuthenticator, settings: DirectorySettings
) -> str:
    try:
        return await directory.discover_base_dn(settings)
    except DirectoryUnavailableError as error:
        # 원인 문구는 서버 내부 정보를 담을 수 있어 단계만 옮긴다
        raise DirectoryVerificationError(error.stage or VerificationStage.CONNECT) from None
