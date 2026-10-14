import hashlib
import logging
from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id, verify_credentials
from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, LOGIN_FAILED
from app.domain.auth.errors import AuthenticationError
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import AmbiguousLoginIdError, UserNotFoundError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.application.ports.directory import DirectoryUser
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.auth.principal import Principal

logger = logging.getLogger(__name__)


def _short_hash(value: str) -> str:
    """로그에 원문 대신 남길 식별용 해시(앞 12자)."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


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
        return await self._issue_session.execute(
            principal
        )  # 사용자 삭제 경쟁은 IssueSession이 변환

    async def _record_login(self, account: LoginId, profile: DirectoryUser) -> Principal:
        async with self._deps.uow_factory() as uow:
            try:
                user = await uow.users.get_active_by_login_id(account)
            except AmbiguousLoginIdError as error:
                logger.warning(
                    "재직 로그인 아이디 중복으로 로그인 거부 count=%d login_id_hash=%s",
                    error.count,
                    _short_hash(account.value),
                )
                raise AuthenticationError(LOGIN_FAILED) from None
            if user is not None:
                user.record_login(
                    self._deps.clock.now(), display_name=profile.display_name, email=profile.email
                )
                try:
                    await uow.users.update(user)
                except UserNotFoundError:  # 조회와 갱신 사이에 삭제됨
                    user = None
                else:
                    await uow.commit()
        if user is None:  # 미등록이거나 로그인 중 삭제됨. 선점한 시도가 실패 1회로 남는다
            raise AuthenticationError(LOGIN_FAILED)
        return user.to_principal()
