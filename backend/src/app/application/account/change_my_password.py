from typing import TYPE_CHECKING

from app.application.auth.dev_login import DEV_LOGIN_IDS
from app.application.auth.messages import LOCAL_MODE_ONLY, LOGIN_REQUIRED, WRONG_CURRENT
from app.application.auth.mode import current_mode
from app.application.auth.tokens import hash_token
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError, WrongCurrentPasswordError
from app.domain.auth.mode import AuthMode
from app.domain.auth.password_policy import ensure_acceptable_password
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import UserNotFoundError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.domain.auth.credentials import Password
    from app.domain.auth.password_hash import PasswordHash
    from app.domain.auth.principal import Principal

DEV_CHANGE_FORBIDDEN = "개발 로그인 전용 사용자의 비밀번호는 바꿀 수 없습니다."


class ChangeMyPassword:
    """local 사용자가 현재 비밀번호를 확인하고 자기 비밀번호를 바꾼다.

    현재 비밀번호 확인은 로그인과 같은 LoginThrottle 카운터를 쓴다(틀리면 실패 1회).
    성공하면 지금 세션은 두고 그 사용자의 다른 세션을 모두 끝낸다.
    """

    def __init__(self, deps: AuthDeps) -> None:
        self._deps = deps

    async def execute(
        self,
        *,
        actor: Principal,
        current: Password,
        new: Password,
        session_token: str,
        client_ip: str,
    ) -> None:
        account = LoginId(actor.subject)
        await self._ensure_changeable(actor)
        ensure_acceptable_password(new, account)
        await self._deps.throttle.ensure_allowed(account, client_ip)
        stored = await self._stored_hash(actor)
        if not await self._deps.hasher.verify(current, stored):
            raise WrongCurrentPasswordError(WRONG_CURRENT)  # 선점한 시도가 실패 1회로 남는다
        await self._deps.throttle.succeeded(account, client_ip)
        new_hash = await self._deps.hasher.hash(new)  # scrypt 동안 트랜잭션을 잡지 않는다
        await self._save(actor, stored, new_hash, hash_token(session_token))

    async def _ensure_changeable(self, actor: Principal) -> None:
        async with self._deps.uow_factory() as uow:
            if await current_mode(uow) is not AuthMode.LOCAL:
                raise InvalidStateError(LOCAL_MODE_ONLY)
        if actor.subject in DEV_LOGIN_IDS:
            raise InvalidStateError(DEV_CHANGE_FORBIDDEN)

    async def _stored_hash(self, actor: Principal) -> PasswordHash | None:
        async with self._deps.uow_factory() as uow:
            return await uow.password_hashes.get(actor.user_id)

    async def _save(
        self, actor: Principal, stored: PasswordHash | None, new_hash: PasswordHash, keep: str
    ) -> None:
        now = self._deps.clock.now()
        async with self._deps.uow_factory() as uow:
            try:
                user = await uow.users.get_for_update(actor.user_id)
                if not user.is_active or await uow.password_hashes.get(actor.user_id) != stored:
                    raise AuthenticationError(LOGIN_REQUIRED)  # 확인 중 퇴사·비밀번호 변경
                await uow.password_hashes.save(actor.user_id, new_hash, now)
            except UserNotFoundError:
                raise AuthenticationError(LOGIN_REQUIRED) from None
            await uow.sessions.delete_others_for_user(actor.user_id, keep)
            await uow.commit()
