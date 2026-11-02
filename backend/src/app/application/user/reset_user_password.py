from typing import TYPE_CHECKING

from app.application.auth.dev_login import DEV_LOGIN_IDS
from app.application.auth.messages import LOCAL_MODE_ONLY
from app.application.auth.mode import current_mode
from app.domain.auth.mode import AuthMode
from app.domain.auth.password_policy import ensure_acceptable_password
from app.domain.common.errors import InvalidStateError
from app.domain.user.messages import ALREADY_RESIGNED

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.password_hasher import PasswordHasher
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.credentials import Password
    from app.domain.auth.principal import Principal
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId

SELF_RESET_FORBIDDEN = "자기 자신의 비밀번호는 내 정보에서 바꾸세요."
DEV_RESET_FORBIDDEN = "개발 로그인 전용 사용자의 비밀번호는 바꿀 수 없습니다."


def _ensure_resettable(target: User, actor: Principal) -> None:
    if not target.is_active:
        raise InvalidStateError(ALREADY_RESIGNED)
    if target.id == actor.user_id:
        raise InvalidStateError(SELF_RESET_FORBIDDEN)
    if target.login_id.value in DEV_LOGIN_IDS:
        raise InvalidStateError(DEV_RESET_FORBIDDEN)


class ResetUserPassword:
    """local 모드에서 admin이 다른 사용자의 비밀번호를 정하고 그 사용자의 모든 로그인을 끝낸다."""

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, hasher: PasswordHasher
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._hasher = hasher

    async def execute(self, *, user_id: UserId, password: Password, actor: Principal) -> None:
        async with self._uow_factory() as uow:
            if await current_mode(uow) is not AuthMode.LOCAL:
                raise InvalidStateError(LOCAL_MODE_ONLY)
            target = await uow.users.get(user_id)
            _ensure_resettable(target, actor)
        ensure_acceptable_password(password, target.login_id)
        password_hash = await self._hasher.hash(password)  # scrypt 동안 트랜잭션을 잡지 않는다
        now = self._clock.now()
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            _ensure_resettable(await uow.users.get_for_update(user_id), actor)
            await uow.password_hashes.save(user_id, password_hash, now)
            await uow.sessions.delete_all_for_user(user_id)
            await uow.commit()
