from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.directory.credentials import resolve_draft
from app.application.directory.errors import DirectoryVerificationError

if TYPE_CHECKING:
    from app.application.directory.verify_settings import VerifyDirectorySettings
    from app.application.ports.directory import VerificationStage
    from app.application.ports.secret_cipher import SecretCipher
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.credentials import Password
    from app.domain.auth.principal import Principal
    from app.domain.directory.settings import DirectorySettingsDraft

SUCCESS_MESSAGE = "AD 설정을 확인했습니다"


@dataclass(frozen=True, slots=True)
class TestResult:
    __test__ = False  # pytest가 수집하지 않도록

    success: bool
    stage: VerificationStage | None
    message: str
    base_dn: str | None = None  # 성공했을 때 찾은 Base DN


class TestDirectorySettings:
    """AD 연결 테스트. 저장하지 않으며, 확인 실패는 예외 대신 결과(단계·안내)로 돌려준다."""

    __test__ = False

    def __init__(
        self, uow_factory: UnitOfWorkFactory, cipher: SecretCipher, verify: VerifyDirectorySettings
    ) -> None:
        self._uow_factory = uow_factory
        self._cipher = cipher
        self._verify = verify

    async def execute(
        self,
        *,
        actor: Principal,
        draft: DirectorySettingsDraft,
        password: Password | None,
        client_ip: str,
    ) -> TestResult:
        async with self._uow_factory() as uow:
            stored = await uow.directory_settings.get()
        settings = resolve_draft(draft, stored, self._cipher)
        try:
            base_dn = await self._verify.execute(
                actor=actor, settings=settings, password=password, client_ip=client_ip
            )
        except DirectoryVerificationError as error:
            return TestResult(success=False, stage=error.stage, message=error.message)
        return TestResult(success=True, stage=None, message=SUCCESS_MESSAGE, base_dn=base_dn)
