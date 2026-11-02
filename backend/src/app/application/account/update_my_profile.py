from typing import TYPE_CHECKING

from app.application.account.get_my_profile import build_my_profile
from app.application.user.profile_edit import apply_profile_changes

if TYPE_CHECKING:
    from app.application.account.get_my_profile import MyProfile
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.user.profile import ProfileChanges


class UpdateMyProfile:
    """로그인한 사용자 자신의 이름·이메일·전화를 고친다(아이디·역할은 바꿀 수 없다)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, *, actor: Principal, changes: ProfileChanges) -> MyProfile:
        user, mode = await apply_profile_changes(
            self._uow_factory, self._clock, actor.user_id, changes
        )
        return build_my_profile(user, mode)
