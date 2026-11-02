from typing import TYPE_CHECKING

from app.application.user.profile_edit import apply_profile_changes

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.user.entities import User
    from app.domain.user.profile import ProfileChanges
    from app.domain.user.value_objects import UserId


class UpdateUserProfile:
    """admin이 재직 사용자의 이름·이메일·전화를 고친다. 아이디·역할은 바꾸지 않는다.

    AD 연동에서는 전화만 가능하다(이름·이메일은 로그인마다 AD 값으로 갱신된다).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, *, user_id: UserId, changes: ProfileChanges, actor: Principal) -> User:
        del actor  # 권한(admin)은 web이 확인한다. 대상은 요청자와 달라도 된다
        target, _ = await apply_profile_changes(self._uow_factory, self._clock, user_id, changes)
        return target
