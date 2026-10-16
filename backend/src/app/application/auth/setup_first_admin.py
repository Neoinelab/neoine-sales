from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id, verify_credentials
from app.application.auth.dev_login import ensure_not_reserved_login_id
from app.application.auth.messages import DIRECTORY_FIRST, SETUP_CLOSED, STORAGE_FIRST
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError
from app.domain.user.entities import User
from app.domain.user.errors import AmbiguousLoginIdError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.application.ports.directory import DirectoryUser
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.directory.settings import DirectorySettings


class SetupFirstAdmin:
    """최초 설정 3단계: AD 계정으로 인증된 사람을 첫 admin으로 등록하고 바로 로그인시킨다."""

    def __init__(self, deps: AuthDeps, issue_session: IssueSession) -> None:
        self._deps = deps
        self._issue_session = issue_session

    async def execute(self, *, login_id: str, password: Password, client_ip: str) -> IssuedSession:
        account = parse_login_id(login_id)
        ensure_not_reserved_login_id(account)
        await self._deps.throttle.ensure_allowed(account, client_ip)
        try:
            settings = await self._load_settings()
        except InvalidStateError:
            await self._deps.throttle.release(account, client_ip)
            raise
        profile = await verify_credentials(self._deps, settings, account, password, client_ip)
        user = await self._register(account, profile)
        await self._deps.throttle.succeeded(account, client_ip)
        return await self._issue_session.execute(user.to_principal())

    async def _load_settings(self) -> DirectorySettings:
        async with self._deps.uow_factory() as uow:
            if await uow.users.count_active_admins() > 0:
                raise InvalidStateError(SETUP_CLOSED)
            stored = await uow.directory_settings.get()
            if stored is None:
                raise InvalidStateError(DIRECTORY_FIRST)
            if await uow.storage_settings.get() is None:
                raise InvalidStateError(STORAGE_FIRST)
        return stored.settings

    async def _register(self, account: LoginId, profile: DirectoryUser) -> User:
        now = self._deps.clock.now()
        async with self._deps.uow_factory() as uow:
            await uow.users.lock_roster()
            if await uow.users.count_active_admins() > 0:
                raise InvalidStateError(SETUP_CLOSED)
            try:
                exists = await uow.users.get_active_by_login_id(account) is not None
            except AmbiguousLoginIdError:  # 이미 둘 이상 있다 = 중복이라는 같은 결론
                exists = True
            if exists:
                raise AlreadyExistsError("사용자", account.value)
            user = User.register_self(account, Role.ADMIN, now=now)
            user.record_login(now, display_name=profile.display_name, email=profile.email)
            await uow.users.add(user)
            await uow.commit()
        return user
