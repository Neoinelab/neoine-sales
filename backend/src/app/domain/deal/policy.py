"""Deal 자격·권한 규칙(Owner 자격, 삭제 권한). 프런트 `permissions.ts`와 같다."""

from typing import TYPE_CHECKING

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId

OWNER_RESIGNED_MESSAGE = "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요."
OWNER_NOT_SALES_MESSAGE = "Owner는 재직 중인 영업 담당자여야 합니다."


def ensure_owner_eligible(user: User | None) -> None:
    """Owner는 재직 중인 sales여야 한다. 퇴사 문구가 역할 문구보다 먼저다."""
    if user is not None and not user.is_active:
        raise InvalidValueError(OWNER_RESIGNED_MESSAGE)
    if user is None or user.role is not Role.SALES:
        raise InvalidValueError(OWNER_NOT_SALES_MESSAGE)


def can_delete_deal(actor_id: UserId, actor_role: Role, owner_id: UserId) -> bool:
    """admin은 모두, sales는 본인이 Owner인 Deal만. 읽기 전용(user)은 불가."""
    if actor_role is Role.ADMIN:
        return True
    return actor_role is Role.SALES and actor_id == owner_id
