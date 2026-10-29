from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id
from app.application.auth.dev_login import DEV_LOGIN_IDS
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
    """후보 AD 설정이 실제로 동작하는지 확인하고 찾은 Base DN을 돌려준다.

    서비스 계정으로 Base DN을 찾은 뒤, 요청한 admin이 새 설정으로 검색·바인드되는지 본다.
    실패하면 DirectoryVerificationError(stage). 허용된 경우 dev-login 사용자(예약 아이디 dev-*)는
    AD 계정이 없으므로 Base DN 탐색까지만 한다. 비밀번호는 로그·예외에 담지 않는다.
    admin 인증이 끝나면 선점한 시도를 되돌리되, 비밀번호가 틀린 경우는 실패 1회로 남긴다.
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
    ) -> str:
        discover_only = self._allow_dev_sessions and actor.subject in DEV_LOGIN_IDS
        if not discover_only and password is None:
            raise InvalidValueError(PASSWORD_REQUIRED)
        base_dn = await self._discover(settings)
        if not discover_only and password is not None:
            await self._authenticate(actor, settings, base_dn, password, client_ip)
        return base_dn

    async def _discover(self, settings: DirectorySettings) -> str:
        try:
            return await self._deps.directory.discover_base_dn(settings)
        except DirectoryUnavailableError as error:
            # 원인 문구는 서버 내부 정보를 담을 수 있어 단계만 옮긴다
            raise DirectoryVerificationError(error.stage or VerificationStage.CONNECT) from None

    async def _authenticate(
        self,
        actor: Principal,
        settings: DirectorySettings,
        base_dn: str,
        password: Password,
        client_ip: str,
    ) -> None:
        account = parse_login_id(actor.subject)
        await self._deps.throttle.ensure_allowed(account, client_ip)
        try:
            await self._deps.directory.authenticate(settings, base_dn, account, password)
        except InvalidCredentialsError as error:  # 선점한 시도가 실패 1회로 남는다
            raise DirectoryVerificationError(error.stage or VerificationStage.BIND) from None
        except DirectoryUnavailableError as error:
            await self._deps.throttle.release(account, client_ip)
            raise DirectoryVerificationError(error.stage or VerificationStage.CONNECT) from None
        await self._deps.throttle.release(account, client_ip)
