from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id, verify_credentials
from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, LOGIN_FAILED
from app.domain.auth.errors import AuthenticationError
from app.domain.common.errors import InvalidStateError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.application.ports.directory import DirectoryUser
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.auth.principal import Principal


class DirectoryLogin:
    """AD 아이디·비밀번호로 로그인한다. 등록된 활성 사용자만 통과한다."""

    def __init__(self, deps: AuthDeps, issue_session: IssueSession) -> None:
        self._deps = deps
        self._issue_session = issue_session

    async def execute(self, *, login_id: str, password: Password, client_ip: str) -> IssuedSession:
        account = parse_login_id(login_id)
        await self._deps.throttle.ensure_allowed(account, client_ip)
        async with self._deps.uow_factory() as uow:
            stored = await uow.directory_settings.get()
        if stored is None:
            await self._deps.throttle.release(account, client_ip)
            raise InvalidStateError(DIRECTORY_NOT_CONFIGURED)
        profile = await verify_credentials(
            self._deps, stored.settings, account, password, client_ip
        )
        principal = await self._record_login(account, profile)
        await self._deps.throttle.succeeded(account, client_ip)
        return await self._issue_session.execute(principal)

    async def _record_login(self, account: LoginId, profile: DirectoryUser) -> Principal:
        async with self._deps.uow_factory() as uow:
            user = await uow.users.get_active_by_login_id(account)
            if user is not None:
                user.record_login(
                    self._deps.clock.now(), display_name=profile.display_name, email=profile.email
                )
                await uow.users.update(user)
                await uow.commit()
        if user is None:  # 선점한 시도가 실패 1회로 남는다
            raise AuthenticationError(LOGIN_FAILED)
        return user.to_principal()
