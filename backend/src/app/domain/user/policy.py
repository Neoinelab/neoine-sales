from typing import TYPE_CHECKING

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.messages import ALREADY_RESIGNED

if TYPE_CHECKING:
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId


def ensure_deletable(
    target: User, *, actor_user_id: UserId | None, active_admin_count: int
) -> None:
    """이미 퇴사한 사용자, 자기 자신, 마지막 활성 admin은 삭제(퇴사·물리)할 수 없다.

    users 행이 없는 요청자는 actor_user_id가 None이다.
    """
    if not target.is_active:
        raise InvalidStateError(ALREADY_RESIGNED)
    if actor_user_id is not None and target.id == actor_user_id:
        raise InvalidStateError("자기 자신은 삭제할 수 없습니다")
    if target.role is Role.ADMIN and active_admin_count <= 1:
        raise InvalidStateError("마지막 관리자는 삭제할 수 없습니다")
