"""사용자 정보 수정(admin)과 본인 정보 수정이 공유하는 규칙: 모드 -> 편집 가능 확인 -> 변경."""

from typing import TYPE_CHECKING

from app.application.auth.mode import current_mode
from app.domain.auth.mode import AuthMode
from app.domain.user.profile import ensure_profile_editable

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User
    from app.domain.user.profile import ProfileChanges
    from app.domain.user.value_objects import UserId


async def apply_profile_changes(
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    user_id: UserId,
    changes: ProfileChanges,
) -> tuple[User, AuthMode]:
    """대상 행을 잠그고 프로필을 바꾼다(바뀐 게 없으면 저장 안 함). (대상, 인증 방식)을 돌려준다."""
    async with uow_factory() as uow:
        mode = await current_mode(uow) or AuthMode.AD
        ensure_profile_editable(changes, mode)
        target = await uow.users.get_for_update(user_id)
        if target.change_profile(changes, clock.now(), require_name=mode is AuthMode.LOCAL):
            await uow.users.update(target)
            await uow.commit()
    return target, mode
