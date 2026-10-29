"""AD가 답할 수 없을 때만 저장된 비밀번호 해시로 로그인시킨다(대체 로그인).

AD가 응답해 비밀번호가 틀렸거나 사용자를 못 찾은 경우는 여기로 오지 않는다. 실패하면 원래 AD
불가 응답을 그대로 올려 아이디의 등록·해시 보유 여부가 응답으로 드러나지 않게 한다.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.auth.log_ids import short_hash
from app.application.auth.warning_stage import DirectoryWarningStage
from app.application.directory.errors import DirectoryCredentialUnreadableError
from app.application.ports.directory import VerificationStage
from app.domain.user.errors import AmbiguousLoginIdError, UserNotFoundError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.ports.directory import DirectoryError
    from app.application.ports.user_repository import UserRepository
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.auth.principal import Principal
    from app.domain.user.entities import User

__all__ = ["DirectoryWarning", "DirectoryWarningStage", "FallbackLogin", "warning_stage_of"]

logger = logging.getLogger(__name__)

_STAGE_BY_VERIFICATION = {
    VerificationStage.CONNECT: DirectoryWarningStage.CONNECT,
    VerificationStage.TLS: DirectoryWarningStage.TLS,
    VerificationStage.SERVICE_BIND: DirectoryWarningStage.SERVICE_BIND,
    VerificationStage.BASE_DN: DirectoryWarningStage.BASE_DN,
    VerificationStage.SEARCH: DirectoryWarningStage.SEARCH,
}


@dataclass(frozen=True, slots=True)
class DirectoryWarning:
    stage: DirectoryWarningStage
    message: str


def warning_stage_of(error: DirectoryError) -> DirectoryWarningStage:
    """AD 오류를 대체 로그인 경고 단계로 바꾼다(단계 정보가 없거나 알 수 없으면 UNKNOWN)."""
    if isinstance(error, DirectoryCredentialUnreadableError):
        return DirectoryWarningStage.CREDENTIAL_UNREADABLE
    if error.stage is None:
        return DirectoryWarningStage.UNKNOWN
    return _STAGE_BY_VERIFICATION.get(error.stage, DirectoryWarningStage.UNKNOWN)


class FallbackLogin:
    """저장된 해시로 인증한다. 실패하면 original을 그대로 다시 올린다(실패 1회로 남는다)."""

    def __init__(self, deps: AuthDeps) -> None:
        self._deps = deps

    async def execute(
        self,
        account: LoginId,
        password: Password,
        *,
        stage: DirectoryWarningStage,
        original: Exception,
    ) -> Principal:
        # scrypt 검증 동안 DB 트랜잭션을 잡지 않도록 읽기 → 검증 → 다시 확인·기록 순서로 나눈다
        async with self._deps.uow_factory() as uow:
            user = await self._active_user(uow.users, account)
            stored = None if user is None else await uow.password_hashes.get(user.id)
        # 사용자·해시가 없어도 verify(None)으로 같은 비용을 쓴다
        matched = await self._deps.hasher.verify(password, stored)
        if user is None or not matched:
            raise original
        async with self._deps.uow_factory() as uow:
            current = await self._active_user(uow.users, account)
            if (
                current is None
                or current.id != user.id
                or await uow.password_hashes.get(current.id) != stored
            ):  # 검증 중 퇴사·교체·해시 변경
                raise original
            current.record_fallback_login(self._deps.clock.now())
            try:
                await uow.users.update(current)
            except UserNotFoundError:  # 조회와 갱신 사이에 삭제됨
                raise original from None
            await uow.commit()
        user = current
        logger.warning(
            "AD 대체 로그인 stage=%s login_id_hash=%s", stage.value, short_hash(account.value)
        )
        return user.to_principal()

    @staticmethod
    async def _active_user(users: UserRepository, account: LoginId) -> User | None:
        try:
            return await users.get_active_by_login_id(account)
        except AmbiguousLoginIdError as error:
            logger.warning(
                "재직 로그인 아이디 중복으로 대체 로그인 거부 count=%d login_id_hash=%s",
                error.count,
                short_hash(account.value),
            )
            return None
