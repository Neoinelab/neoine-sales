"""첨부 삭제·교체 권한.

admin은 모두, sales는 본인 또는 퇴사한 sales의 파일, 읽기 전용(user)은 불가.
"""

from typing import TYPE_CHECKING

from app.domain.auth.principal import Role

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId, UserRef


def can_delete_attachment(user_id: UserId, role: Role, uploader: UserRef) -> bool:
    if role is Role.ADMIN:
        return True
    if role is not Role.SALES:
        return False
    return uploader.id == user_id or (uploader.resigned and uploader.role is Role.SALES)
