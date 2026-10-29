"""미팅 기록 수정·삭제 권한: admin은 모두, sales는 본인 기록만, 읽기 전용(user)은 불가."""

from typing import TYPE_CHECKING

from app.domain.auth.principal import Role

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId


def can_edit_meeting(user_id: UserId, role: Role, author_id: UserId) -> bool:
    if role is Role.ADMIN:
        return True
    return role is Role.SALES and user_id == author_id
