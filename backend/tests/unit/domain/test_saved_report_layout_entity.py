"""Report 엔티티와 결과 배치: 만들기·덮어쓰기·복제와 배치만 바꾸기(change_layout).

change_layout의 판정 순서는 볼 수 있는가(404) -> 고칠 수 있는가(403) -> revision(409)이다.
현재 정책에서는 볼 수 있으면 고칠 수 있으므로(`can_edit_report`) 403은 정책을 바꿔야만 닿는다.
순서 검증은 `app.domain.saved_report.entities.can_edit_report`를 막는 것으로 만든다(계약:
change_layout은 그 모듈의 `can_edit_report`로 판정한다).
"""

import pytest

from app.domain.auth.principal import Role
from app.domain.saved_report import entities
from app.domain.saved_report.entities import Report
from app.domain.saved_report.errors import (
    ReportEditConflictError,
    ReportEditForbiddenError,
    ReportNotFoundError,
)
from app.domain.saved_report.layout import DEFAULT_LAYOUT
from app.domain.saved_report.values import ReportId, ReportVisibility
from tests.factories import NOW, later
from tests.factories_report import make_broken_report, make_content, make_report
from tests.support.chart_defs import raw_chart
from tests.support.ids import new_id
from tests.support.layout_defs import make_layout
from tests.support.report_defs import col, raw
from tests.support.user_ids import uid

OWNER = uid("layout-owner")
OTHER = uid("layout-other")
SIDE = make_layout("chart", ("chart", "table"), "side_by_side")
TABLE_ONLY = make_layout("table", ("table", "chart"), "stacked")


def test_create_without_layout_uses_default() -> None:
    """배치 없이 만들면 기본 배치다.

    테스트 코드: RS-038
    """
    # when: 배치 없는 내용으로 만든다
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(), owner=OWNER, now=NOW
    )
    # then: 기본 배치다
    assert report.layout == DEFAULT_LAYOUT


def test_create_with_layout_keeps_it() -> None:
    """배치를 정해 만들면 그 배치다.

    테스트 코드: RS-038
    """
    # when: 배치가 있는 내용으로 만든다
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(layout=SIDE), owner=OWNER, now=NOW
    )
    # then: 그 배치다
    assert report.layout == SIDE


def test_a_report_made_without_layout_has_the_default() -> None:
    """테스트 팩토리로 배치 없이 만든 리포트도 기본 배치를 가진다."""
    # when: 배치를 주지 않은 리포트의 배치를 읽는다
    layout = make_report(owner=OWNER).layout
    # then: 기본 배치다
    assert layout == DEFAULT_LAYOUT


def test_overwrite_without_layout_keeps_stored_layout() -> None:
    """배치 없이 덮어쓰면 저장된 배치가 남는다.

    테스트 코드: RS-040
    """
    # given: 배치 CHART_SIDE인 리포트
    report = make_report(owner=OWNER, layout=SIDE)
    # when: 배치 없는 내용으로 덮어쓴다
    report.overwrite(
        make_content("바꿈"), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )
    # then: 배치는 그대로, revision은 2다
    assert report.layout == SIDE
    assert report.revision == 2


def test_overwrite_with_layout_replaces_it() -> None:
    """배치를 보내 덮어쓰면 배치가 바뀐다.

    테스트 코드: RS-040
    """
    # given: 배치 CHART_SIDE인 리포트
    report = make_report(owner=OWNER, layout=SIDE)
    # when: TABLE_ONLY 배치로 덮어쓴다
    report.overwrite(
        make_content("바꿈", layout=TABLE_ONLY),
        editor=OWNER,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )
    # then: 배치가 TABLE_ONLY다
    assert report.layout == TABLE_ONLY


def test_rejected_overwrite_keeps_the_layout() -> None:
    """거절된 덮어쓰기는 배치를 바꾸지 않는다.

    테스트 코드: RS-040
    """
    # given: revision 3, 배치 CHART_SIDE인 리포트
    report = make_report(owner=OWNER, layout=SIDE, revision=3)
    # when·then: 낡은 revision으로 덮어쓰면 충돌이다
    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content(layout=TABLE_ONLY),
            editor=OWNER,
            role=Role.SALES,
            expected_revision=2,
            now=later(1),
        )
    # then: 배치가 그대로다
    assert report.layout == SIDE


def test_copy_as_copies_layout() -> None:
    """복제본은 원본의 배치를 가져가고 원본 배치는 그대로다.

    테스트 코드: RS-028
    """
    # given: 배치 CHART_SIDE인 원본
    source = make_report(owner=OWNER, layout=SIDE)
    # when: 복제한다
    copied = source.copy_as(
        entity_id=ReportId(new_id()),
        meta_name="복사본",
        meta_description="",
        visibility=ReportVisibility.PUBLIC,
        generated_sql="SELECT 1",
        owner=OTHER,
        now=later(1),
    )
    # then: 복제본과 원본의 배치가 같다
    assert copied.layout == SIDE
    assert source.layout == SIDE


def test_change_layout_hidden_report_raises_not_found() -> None:
    """남의 비공개 리포트의 배치 저장은 404이고 배치는 그대로다.

    테스트 코드: RS-014
    """
    # given: 남의 비공개 리포트
    report = make_report(owner=OWNER, visibility="private")
    # when·then: sales·user가 배치를 바꾸면 모두 찾을 수 없음 오류다
    for role in (Role.SALES, Role.USER):
        with pytest.raises(ReportNotFoundError):
            report.change_layout(SIDE, editor=OTHER, role=role, expected_revision=1, now=later(1))
    # then: 배치·revision이 그대로다
    assert (report.layout, report.revision) == (DEFAULT_LAYOUT, 1)


def test_change_layout_without_edit_right_raises_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """수정 권한이 없으면 배치 저장은 403이다(지금 규칙으로는 닿지 않는 방어).

    테스트 코드: RS-046
    """
    # given: 수정 권한 판정을 거짓으로 바꾼 상태의 공개 리포트
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report(owner=OWNER, visibility="public")
    # when·then: 배치를 바꾸면 수정 권한 오류다
    with pytest.raises(ReportEditForbiddenError):
        report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(1))
    # then: 배치·revision이 그대로다
    assert (report.layout, report.revision) == (DEFAULT_LAYOUT, 1)


def test_change_layout_stale_revision_raises_conflict() -> None:
    """낡은 revision으로 배치를 저장하면 충돌이다.

    테스트 코드: RS-042
    """
    # given: revision 3인 리포트
    report = make_report(owner=OWNER, revision=3)
    # when·then: revision 2로 배치를 바꾸면 충돌이다
    with pytest.raises(ReportEditConflictError):
        report.change_layout(SIDE, editor=OWNER, role=Role.SALES, expected_revision=2, now=later(1))
    # then: 배치·revision이 그대로다
    assert (report.layout, report.revision) == (DEFAULT_LAYOUT, 3)


def test_change_layout_checks_forbidden_before_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """수정 권한 판정(403)이 revision 판정(409)보다 먼저다.

    테스트 코드: RS-046
    """
    # given: 수정 권한 판정을 거짓으로 바꾼 상태의 revision 3 리포트
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report(owner=OWNER, revision=3)
    # when·then: 낡은 revision으로 배치를 바꾸면 수정 권한 오류다
    with pytest.raises(ReportEditForbiddenError):
        report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(1))


def test_change_layout_checks_not_found_before_stale_revision() -> None:
    """볼 수 없는 리포트는 낡은 revision이어도 404가 먼저다.

    테스트 코드: RS-046
    """
    # given: revision 3인 남의 비공개 리포트
    report = make_report(owner=OWNER, visibility="private", revision=3)
    # when·then: 낡은 revision으로 배치를 바꾸면 찾을 수 없음 오류다
    with pytest.raises(ReportNotFoundError):
        report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(1))


def test_change_layout_updates_layout_revision_editor_time_only() -> None:
    """배치 저장은 배치·revision·최종 수정자·수정 시각만 바꾼다.

    테스트 코드: RS-041
    """
    # given: 차트와 정의가 있는 revision 4의 공개 리포트
    chart = raw_chart("bar", 0, [1])
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    report = make_report(
        "원본", owner=OWNER, visibility="public", definition=definition, chart=chart, revision=4
    )
    before = (report.name, report.description, report.visibility, report.generated_sql)
    # when: 다른 사용자가 배치를 바꾼다
    report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=4, now=later(9))
    # then: 배치·revision·최종 수정자·수정 시각이 바뀐다
    assert report.layout == SIDE
    assert report.revision == 5
    assert report.updated_by_user_id == OTHER
    assert report.updated_at == later(9)
    # then: 만든 사람·생성 시각·정의·차트·이름·설명·공개 범위·SQL은 그대로다
    assert report.owner_user_id == OWNER
    assert report.created_at == NOW
    assert report.definition == definition
    assert report.chart == chart
    assert (report.name, report.description, report.visibility, report.generated_sql) == before


def test_change_layout_keeps_a_broken_definition_and_chart_flag() -> None:
    """깨진 정의·읽을 수 없는 차트의 리포트도 배치 저장으로 그 상태가 바뀌지 않는다.

    테스트 코드: RS-041
    """
    # given: 정의가 깨지고 차트를 읽을 수 없는 리포트
    report = make_broken_report(owner=OWNER, chart_unreadable=True)
    # when: 배치를 바꾼다
    report.change_layout(SIDE, editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1))
    # then: 배치만 바뀌고 정의 None·차트 없음·읽을 수 없음이 그대로다
    assert report.layout == SIDE
    assert report.definition is None
    assert report.chart is None
    assert report.chart_unreadable is True
