"""저장 리포트 권한 판정. 보기·수정·삭제·공개 범위 변경 규칙의 정본."""

from typing import TYPE_CHECKING

from app.domain.auth.principal import Role
from app.domain.saved_report.values import ReportListScope, ReportVisibility

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId


def can_view_report(
    user_id: UserId, role: Role, *, owner_id: UserId, visibility: ReportVisibility
) -> bool:
    return role is Role.ADMIN or user_id == owner_id or visibility is ReportVisibility.PUBLIC


def can_edit_report(
    user_id: UserId, role: Role, *, owner_id: UserId, visibility: ReportVisibility
) -> bool:
    """공개된 리포트는 누구나 고칠 수 있다. 비공개는 만든 사람과 admin만 본다(고친다)."""
    return can_view_report(user_id, role, owner_id=owner_id, visibility=visibility)


def can_delete_report(user_id: UserId, role: Role, *, owner_id: UserId) -> bool:
    return role is Role.ADMIN or user_id == owner_id


def can_change_report_visibility(user_id: UserId, role: Role, *, owner_id: UserId) -> bool:
    return role is Role.ADMIN or user_id == owner_id


def list_scope(user_id: UserId, role: Role) -> ReportListScope:
    return ReportListScope(viewer_id=user_id, see_all=role is Role.ADMIN)
