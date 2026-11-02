from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id
from app.application.auth.directory_login import DirectoryLogin, LoginOutcome
from app.application.auth.local_login import LocalLogin
from app.application.auth.mode import current_mode
from app.domain.auth.mode import AuthMode

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
