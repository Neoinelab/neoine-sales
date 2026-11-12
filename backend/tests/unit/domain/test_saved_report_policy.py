"""저장 리포트 권한: 보기·수정·공개 범위 변경·삭제를 역할과 소유로 판정한다.

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
    (Role.ADMIN, False, PRIVATE, True, True, True, True),  # admin은 남의 비공개도 본다
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
    """역할·소유·공개 범위마다 보기·수정·공개 범위 변경·삭제 판정이 결정 표와 같다."""
    # given: 표의 한 행(역할, 내 것 여부, 공개 범위)
    role, mine, visibility, view, edit, change, delete = row
    owner = ME if mine else OTHER
    # when: 네 판정을 구한다
    can_view = can_view_report(ME, role, owner_id=owner, visibility=visibility)
    can_edit = can_edit_report(ME, role, owner_id=owner, visibility=visibility)
    can_change = can_change_report_visibility(ME, role, owner_id=owner)
    can_delete = can_delete_report(ME, role, owner_id=owner)
    # then: 표의 기대값과 같다
    assert can_view is view
    assert can_edit is edit
    assert can_change is change
    assert can_delete is delete


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
def test_non_admin_list_scope_is_limited_to_the_viewer(role: Role) -> None:
    """admin이 아닌 역할의 목록 범위는 요청자 기준이다(전부 보기가 아니다)."""
    # when: sales 또는 user의 목록 범위를 만든다
    scope = list_scope(ME, role)
    # then: 요청자 id를 쓰고 전부 보기가 아니다
    assert scope.viewer_id == ME
    assert scope.see_all is False


def test_admin_list_scope_sees_everything() -> None:
    """admin의 목록 범위는 전부 보기다."""
    # when: admin의 목록 범위를 만든다
    scope = list_scope(ME, Role.ADMIN)
    # then: 전부 보기다
    assert scope.viewer_id == ME
    assert scope.see_all is True
