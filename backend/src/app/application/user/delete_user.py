from typing import TYPE_CHECKING

from app.domain.auth.credentials import LoginId
from app.domain.common.errors import InvalidValueError
from app.domain.user.policy import ensure_deletable

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.user.value_objects import UserId


def _actor_login_id(actor: Principal) -> LoginId | None:
    """dev admin(`dev:admin`)처럼 로그인 아이디 형식이 아닌 subject는 users 행이 없는 요청자다."""
    try:
        return LoginId(actor.subject)
    except InvalidValueError:
        return None


class DeleteUser:
    """사용자의 세션을 모두 폐기한 뒤 사용자를 물리 삭제한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, *, user_id: UserId, actor: Principal) -> None:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            target = await uow.users.get(user_id)
            ensure_deletable(
                target,
                actor_login_id=_actor_login_id(actor),
                active_admin_count=await uow.users.count_active_admins(),
            )
            await uow.sessions.revoke_all_for_subject(target.login_id.value, now)
            await uow.users.delete(user_id)
            await uow.commit()
