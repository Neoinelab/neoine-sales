"""Comment 권한 규칙: 삭제는 admin 모두·sales 본인(user 불가), 읽음 처리는 Deal Owner만."""

from typing import TYPE_CHECKING

from app.domain.auth.principal import Role

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId


def can_delete_comment(user_id: UserId, role: Role, author_id: UserId) -> bool:
    if role is Role.ADMIN:
        return True
    return role is Role.SALES and user_id == author_id


def can_mark_comments_read(user_id: UserId, deal_owner_id: UserId) -> bool:
    """역할과 무관하게 그 Deal의 현재 Owner 본인만(CM-R27)."""
    return user_id == deal_owner_id
