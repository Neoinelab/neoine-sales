from typing import TYPE_CHECKING

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId
    from app.domain.user.entities import User


def ensure_deletable(
    target: User, *, actor_login_id: LoginId | None, active_admin_count: int
) -> None:
    """자기 자신과 마지막 활성 admin은 삭제할 수 없다. users 행이 없는 요청자(dev admin)는 None."""
    if actor_login_id is not None and target.login_id == actor_login_id:
        raise InvalidStateError("자기 자신은 삭제할 수 없습니다")
    if target.role is Role.ADMIN and active_admin_count <= 1:
        raise InvalidStateError("마지막 관리자는 삭제할 수 없습니다")
