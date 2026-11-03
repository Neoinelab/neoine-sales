from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id
from app.application.auth.directory_login import DirectoryLogin, LoginOutcome
from app.application.auth.local_login import LocalLogin
from app.application.auth.messages import LOGIN_FAILED
from app.application.auth.mode import current_mode
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.mode import AuthMode
from app.domain.common.errors import InvalidValueError
from app.domain.user.retired_login_ids import is_retired_dev_login_id

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.issue_session import IssueSession
    from app.domain.auth.credentials import Password


class PasswordLogin:
    """로그인 진입점. local 모드는 저장 해시로, 그 외(AD·미선택)는 기존 AD 로그인으로 보낸다.

    local 로그인도 AD 로그인과 같은 LoginThrottle 카운터를 쓴다(아이디·IP).
    """

    def __init__(self, deps: AuthDeps, issue_session: IssueSession) -> None:
        self._deps = deps
        self._issue_session = issue_session
        self._directory = DirectoryLogin(deps, issue_session)
        self._local = LocalLogin(deps)

    async def execute(self, *, login_id: str, password: Password, client_ip: str) -> LoginOutcome:
        await self._reject_retired(login_id, client_ip)
        async with self._deps.uow_factory() as uow:
            mode = await current_mode(uow)
        if mode is not AuthMode.LOCAL:
            return await self._directory.execute(
                login_id=login_id, password=password, client_ip=client_ip
            )
        account = parse_login_id(login_id)
        await self._deps.throttle.ensure_allowed(account, client_ip)
        principal = await self._local.execute(account, password)
        await self._deps.throttle.succeeded(account, client_ip)
        session = await self._issue_session.execute(principal)
        return LoginOutcome(session, None)

    async def _reject_retired(self, login_id: str, client_ip: str) -> None:
        """폐지된 개발 로그인 아이디는 AD·해시를 거치지 않고 일반 실패 1회로 거부한다."""
        try:
            account = LoginId(login_id)
        except InvalidValueError:
            return  # 형식 오류는 기존 흐름이 같은 문구로 거부한다
        if is_retired_dev_login_id(account):
            await self._deps.throttle.ensure_allowed(account, client_ip)
            raise AuthenticationError(LOGIN_FAILED)
