"""Report 엔티티와 결과 배치(AC24, 26, 28): 만들기·덮어쓰기·복제와 배치만 바꾸기(change_layout).

change_layout의 판정 순서는 볼 수 있는가(404) -> 고칠 수 있는가(403) -> revision(409)이다.
현재 정책에서는 볼 수 있으면 고칠 수 있으므로(`can_edit_report`) 403은 정책을 바꿔야만 닿는다.
순서 검증은 `app.domain.saved_report.entities.can_edit_report`를 막는 것으로 만든다(계약:
change_layout은 그 모듈의 `can_edit_report`로 판정한다).
"""

import pytest
from app.domain.saved_report.layout import DEFAULT_LAYOUT

from app.domain.auth.principal import Role
from app.domain.saved_report import entities
from app.domain.saved_report.entities import Report
from app.domain.saved_report.errors import (
    ReportEditConflictError,
    ReportEditForbiddenError,
    ReportNotFoundError,
)
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
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(), owner=OWNER, now=NOW
    )

    assert report.layout == DEFAULT_LAYOUT


def test_create_with_layout_keeps_it() -> None:
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(layout=SIDE), owner=OWNER, now=NOW
    )

    assert report.layout == SIDE


def test_a_report_made_without_layout_has_the_default() -> None:
    assert make_report(owner=OWNER).layout == DEFAULT_LAYOUT


def test_overwrite_without_layout_keeps_stored_layout() -> None:
    report = make_report(owner=OWNER, layout=SIDE)

    report.overwrite(
        make_content("바꿈"), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )

    assert report.layout == SIDE
    assert report.revision == 2


def test_overwrite_with_layout_replaces_it() -> None:
    report = make_report(owner=OWNER, layout=SIDE)

    report.overwrite(
        make_content("바꿈", layout=TABLE_ONLY),
        editor=OWNER,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    assert report.layout == TABLE_ONLY


def test_rejected_overwrite_keeps_the_layout() -> None:
    report = make_report(owner=OWNER, layout=SIDE, revision=3)

    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content(layout=TABLE_ONLY),
            editor=OWNER,
            role=Role.SALES,
            expected_revision=2,
            now=later(1),
        )

    assert report.layout == SIDE


def test_copy_as_copies_layout() -> None:
    source = make_report(owner=OWNER, layout=SIDE)

    copied = source.copy_as(
        entity_id=ReportId(new_id()),
        meta_name="복사본",
        meta_description="",
        visibility=ReportVisibility.PUBLIC,
        generated_sql="SELECT 1",
        owner=OTHER,
        now=later(1),
    )

    assert copied.layout == SIDE
    assert source.layout == SIDE


def test_change_layout_hidden_report_raises_not_found() -> None:
    report = make_report(owner=OWNER, visibility="private")

    for role in (Role.SALES, Role.USER):
        with pytest.raises(ReportNotFoundError):
            report.change_layout(SIDE, editor=OTHER, role=role, expected_revision=1, now=later(1))

    assert (report.layout, report.revision) == (DEFAULT_LAYOUT, 1)


def test_change_layout_without_edit_right_raises_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report(owner=OWNER, visibility="public")

    with pytest.raises(ReportEditForbiddenError):
        report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(1))

    assert (report.layout, report.revision) == (DEFAULT_LAYOUT, 1)


def test_change_layout_stale_revision_raises_conflict() -> None:
    report = make_report(owner=OWNER, revision=3)

    with pytest.raises(ReportEditConflictError):
        report.change_layout(SIDE, editor=OWNER, role=Role.SALES, expected_revision=2, now=later(1))

    assert (report.layout, report.revision) == (DEFAULT_LAYOUT, 3)


def test_change_layout_checks_forbidden_before_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report(owner=OWNER, revision=3)

    with pytest.raises(ReportEditForbiddenError):
        report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(1))


def test_change_layout_checks_not_found_before_stale_revision() -> None:
    report = make_report(owner=OWNER, visibility="private", revision=3)

    with pytest.raises(ReportNotFoundError):
        report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(1))


def test_change_layout_updates_layout_revision_editor_time_only() -> None:
    chart = raw_chart("bar", 0, [1])
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    report = make_report(
        "원본", owner=OWNER, visibility="public", definition=definition, chart=chart, revision=4
    )
    before = (report.name, report.description, report.visibility, report.generated_sql)

    report.change_layout(SIDE, editor=OTHER, role=Role.SALES, expected_revision=4, now=later(9))

    assert report.layout == SIDE
    assert report.revision == 5
    assert report.updated_by_user_id == OTHER
    assert report.updated_at == later(9)
    assert report.owner_user_id == OWNER
    assert report.created_at == NOW
    assert report.definition == definition
    assert report.chart == chart
    assert (report.name, report.description, report.visibility, report.generated_sql) == before


def test_change_layout_keeps_a_broken_definition_and_chart_flag() -> None:
    report = make_broken_report(owner=OWNER, chart_unreadable=True)

    report.change_layout(SIDE, editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1))

    assert report.layout == SIDE
    assert report.definition is None
    assert report.chart is None
    assert report.chart_unreadable is True
