from typing import TYPE_CHECKING

from app.application.auth.dev_login import DEV_LOGIN_IDS
from app.domain.common.errors import InvalidStateError
from app.domain.user.policy import ensure_role_changeable

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal, Role
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId

DEV_USER_ROLE_CHANGE = "개발 로그인 전용 사용자의 역할은 바꿀 수 없습니다."


class ChangeUserRole:
    """재직 사용자의 역할을 바꾼다. 세션은 건드리지 않는다(역할은 요청마다 users 행에서 읽는다).

    마지막 admin 보호를 위해 DeleteUser와 같이 roster를 먼저 잠근다. 같은 역할이면 저장하지 않는다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, *, user_id: UserId, role: Role, actor: Principal) -> User:
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()  # 잠금 순서: roster -> 대상 users 행
            target = await uow.users.get_for_update(user_id)
            ensure_role_changeable(
                target,
                role,
                actor_user_id=actor.user_id,
                active_admin_count=await uow.users.count_active_admins(),
            )
            if target.login_id.value in DEV_LOGIN_IDS:
                raise InvalidStateError(DEV_USER_ROLE_CHANGE)
            if target.change_role(role, self._clock.now()):
                await uow.users.update(target)
                await uow.commit()
        return target
