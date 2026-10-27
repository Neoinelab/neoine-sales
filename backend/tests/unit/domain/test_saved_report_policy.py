"""저장 리포트 권한(계획 4.3 표): 보기·수정·공개 범위 변경·삭제를 역할과 소유로 판정한다.

기대값은 결정 표를 그대로 옮긴 것이다(구현 규칙을 되풀이하지 않는다).
"""

import pytest

from app.domain.auth.principal import Role
from app.domain.saved_report.policy import (
    can_change_report_visibility,
    can_delete_report,
    can_edit_report,
    can_view_report,
    list_scope,
)
from app.domain.saved_report.values import ReportVisibility
from tests.support.user_ids import uid

ME = uid("report-me")
OTHER = uid("report-other")
PUBLIC = ReportVisibility.PUBLIC
PRIVATE = ReportVisibility.PRIVATE

# (역할, 내 것인가, 공개 범위, 보기, 수정, 공개 범위 변경, 삭제)
Row = tuple[Role, bool, ReportVisibility, bool, bool, bool, bool]
TABLE: list[Row] = [
    (Role.ADMIN, True, PUBLIC, True, True, True, True),
    (Role.ADMIN, True, PRIVATE, True, True, True, True),
    (Role.ADMIN, False, PUBLIC, True, True, True, True),
    (Role.ADMIN, False, PRIVATE, True, True, True, True),  # Q1=A: admin은 남의 비공개도 본다
    (Role.SALES, True, PUBLIC, True, True, True, True),
    (Role.SALES, True, PRIVATE, True, True, True, True),
    (Role.SALES, False, PUBLIC, True, True, False, False),  # 수정은 되고 삭제·공개 변경은 안 된다
    (Role.SALES, False, PRIVATE, False, False, False, False),
    (Role.USER, True, PUBLIC, True, True, True, True),
    (Role.USER, True, PRIVATE, True, True, True, True),
    (Role.USER, False, PUBLIC, True, True, False, False),
    (Role.USER, False, PRIVATE, False, False, False, False),
]


@pytest.mark.parametrize(
    "row", TABLE, ids=[f"{r[0].value}-{'mine' if r[1] else 'other'}-{r[2].value}" for r in TABLE]
)
def test_report_permissions_follow_the_user_decision(row: Row) -> None:
    role, mine, visibility, view, edit, change, delete = row
    owner = ME if mine else OTHER

    assert can_view_report(ME, role, owner_id=owner, visibility=visibility) is view
    assert can_edit_report(ME, role, owner_id=owner, visibility=visibility) is edit
    assert can_change_report_visibility(ME, role, owner_id=owner) is change
    assert can_delete_report(ME, role, owner_id=owner) is delete


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
def test_non_admin_list_scope_is_limited_to_the_viewer(role: Role) -> None:
    scope = list_scope(ME, role)

    assert scope.viewer_id == ME
    assert scope.see_all is False


def test_admin_list_scope_sees_everything() -> None:
    scope = list_scope(ME, Role.ADMIN)

    assert scope.viewer_id == ME
    assert scope.see_all is True
