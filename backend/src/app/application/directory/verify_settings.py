from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id
from app.application.auth.dev_login import DEV_SUBJECT_PREFIX
from app.application.directory.errors import DirectoryVerificationError
from app.application.ports.directory import (
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.domain.auth.credentials import Password
    from app.domain.auth.principal import Principal
    from app.domain.directory.settings import DirectorySettings

PASSWORD_REQUIRED = "AD 설정을 확인하려면 현재 관리자의 비밀번호가 필요합니다"  # noqa: S105


class VerifyDirectorySettings:
    """후보 AD 설정이 실제로 동작하는지 확인한다. 실패하면 DirectoryVerificationError(stage).

    요청한 admin이 새 설정으로 AD 인증에 성공해야 통과한다. 허용된 경우 dev-login admin은
    users 행·AD 계정이 없으므로 연결 확인(probe)만 한다. 비밀번호는 로그·예외에 담지 않는다.
    성공하면 선점한 시도를 1회 되돌린다(계정 카운터는 지우지 않는다).
    """

    def __init__(self, deps: AuthDeps, *, allow_dev_sessions: bool) -> None:
        self._deps = deps
        self._allow_dev_sessions = allow_dev_sessions

    async def execute(
        self,
        *,
        actor: Principal,
        settings: DirectorySettings,
        password: Password | None,
        client_ip: str,
    ) -> None:
        if self._allow_dev_sessions and actor.subject.startswith(DEV_SUBJECT_PREFIX):
            await self._probe(settings)
            return
        if password is None:
            raise InvalidValueError(PASSWORD_REQUIRED)
        await self._authenticate(actor, settings, password, client_ip)

    async def _probe(self, settings: DirectorySettings) -> None:
        try:
            await self._deps.directory.probe(settings)
        except DirectoryUnavailableError as error:
            raise DirectoryVerificationError(error.stage or VerificationStage.CONNECT) from None

    async def _authenticate(
        self, actor: Principal, settings: DirectorySettings, password: Password, client_ip: str
    ) -> None:
        account = parse_login_id(actor.subject)
        await self._deps.throttle.ensure_allowed(account, client_ip)
        try:
            await self._deps.directory.authenticate(settings, account, password)
        except InvalidCredentialsError:  # 선점한 시도가 실패 1회로 남는다
            raise DirectoryVerificationError(VerificationStage.BIND) from None
        except DirectoryUnavailableError as error:
            await self._deps.throttle.release(account, client_ip)
            raise DirectoryVerificationError(error.stage or VerificationStage.CONNECT) from None
        await self._deps.throttle.release(account, client_ip)
