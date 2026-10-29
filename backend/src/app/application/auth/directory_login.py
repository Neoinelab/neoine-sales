import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.auth.credential_check import parse_login_id
from app.application.auth.fallback_login import (
    DirectoryWarning,
    DirectoryWarningStage,
    FallbackLogin,
    warning_stage_of,
)
from app.application.auth.log_ids import short_hash
from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, FALLBACK_MESSAGES, LOGIN_FAILED
from app.application.directory.credentials import unseal_settings
from app.application.ports.directory import DirectoryUnavailableError, InvalidCredentialsError
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import AmbiguousLoginIdError, UserNotFoundError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.application.ports.directory import DirectoryUser
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.auth.password_hash import PasswordHash
    from app.domain.auth.principal import Principal

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoginOutcome:
    session: IssuedSession
    directory_warning: DirectoryWarning | None  # admin이 대체 로그인으로 들어왔을 때만


class DirectoryLogin:
    """AD 아이디·비밀번호로 로그인한다. 등록된 활성 사용자만 통과한다.

    AD가 답할 수 없을 때만(설정 없음, 연결·TLS·서비스 계정·Base DN 실패, 검색 2건 이상, 비밀번호
    복호화 실패) 저장된 해시로 대체 로그인한다. AD가 비밀번호를 거절하면 해시가 맞아도 거부한다.
    """

    def __init__(self, deps: AuthDeps, issue_session: IssueSession) -> None:
        self._deps = deps
        self._issue_session = issue_session
        self._fallback = FallbackLogin(deps)

    async def execute(self, *, login_id: str, password: Password, client_ip: str) -> LoginOutcome:
        account = parse_login_id(login_id)
        await self._deps.throttle.ensure_allowed(account, client_ip)
        principal, stage = await self._sign_in(account, password)
        await self._deps.throttle.succeeded(account, client_ip)
        session = await self._issue_session.execute(principal)  # 삭제 경쟁은 IssueSession이 변환
        return LoginOutcome(session, self._warning(principal, stage))

    async def _sign_in(
        self, account: LoginId, password: Password
    ) -> tuple[Principal, DirectoryWarningStage | None]:
        """(주체, 대체 로그인이었다면 그 이유). AD 로그인이면 이유는 None."""
        async with self._deps.uow_factory() as uow:
            stored = await uow.directory_settings.get()
        failure: DirectoryUnavailableError | InvalidStateError
        if stored is None:
            stage = DirectoryWarningStage.NOT_CONFIGURED
            failure = InvalidStateError(DIRECTORY_NOT_CONFIGURED)
        else:
            try:
                settings = unseal_settings(self._deps.cipher, stored)
                profile = await self._deps.directory.authenticate(
                    settings, stored.base_dn, account, password
                )
            except InvalidCredentialsError:  # 선점한 시도가 실패 1회로 남는다. 대체 로그인 없음
                raise AuthenticationError(LOGIN_FAILED) from None
            except DirectoryUnavailableError as error:
                stage, failure = warning_stage_of(error), error
            else:
                password_hash = await self._deps.hasher.hash(password)
                return await self._record_login(account, profile, password_hash), None
        principal = await self._fallback.execute(account, password, stage=stage, original=failure)
        return principal, stage

    @staticmethod
    def _warning(
        principal: Principal, stage: DirectoryWarningStage | None
    ) -> DirectoryWarning | None:
        if stage is None or principal.role is not Role.ADMIN:
            return None
        return DirectoryWarning(stage, FALLBACK_MESSAGES[stage])

    async def _record_login(
        self, account: LoginId, profile: DirectoryUser, password_hash: PasswordHash
    ) -> Principal:
        now = self._deps.clock.now()
        async with self._deps.uow_factory() as uow:
            try:
                user = await uow.users.get_active_by_login_id(account)
            except AmbiguousLoginIdError as error:
                logger.warning(
                    "재직 로그인 아이디 중복으로 로그인 거부 count=%d login_id_hash=%s",
                    error.count,
                    short_hash(account.value),
                )
                raise AuthenticationError(LOGIN_FAILED) from None
            if user is not None:
                user.record_login(now, display_name=profile.display_name, email=profile.email)
                try:
                    await uow.users.update(user)
                    await uow.password_hashes.save(user.id, password_hash, now)
                except UserNotFoundError:  # 조회와 갱신 사이에 삭제됨
                    user = None
                else:
                    await uow.commit()
        if user is None:  # 미등록이거나 로그인 중 삭제됨. 선점한 시도가 실패 1회로 남는다
            raise AuthenticationError(LOGIN_FAILED)
        return user.to_principal()
