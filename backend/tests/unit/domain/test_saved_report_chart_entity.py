"""Report 엔티티와 차트 (Reports 4단계 AC1·5·6·7·8): 만들기·덮어쓰기·복제와 목록용 종류."""

import pytest
from app.domain.report.chart import ChartKind

from app.domain.auth.principal import Role
from app.domain.saved_report.entities import Report
from app.domain.saved_report.values import ReportId, ReportVisibility
from tests.factories import NOW, later
from tests.factories_report import make_content, make_report
from tests.support.chart_defs import raw_chart
from tests.support.ids import new_id
from tests.support.user_ids import uid

OWNER = uid("chart-owner")
OTHER = uid("chart-other")
BAR = raw_chart("bar", 0, [1])
STACKED = raw_chart("stacked_bar", 0, [2], series=1)


def test_a_new_report_has_no_chart_by_default() -> None:
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(), owner=OWNER, now=NOW
    )

    assert report.chart is None
    assert report.chart_unreadable is False


def test_create_keeps_the_chart_of_the_content() -> None:
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(chart=BAR), owner=OWNER, now=NOW
    )

    assert report.chart == BAR
    assert report.chart_unreadable is False


def test_overwrite_replaces_the_chart_and_bumps_the_revision() -> None:
    report = make_report(owner=OWNER, visibility="public", chart=BAR)

    report.overwrite(
        make_content(chart=STACKED),
        editor=OTHER,
        role=Role.SALES,
        expected_revision=1,
        now=later(5),
    )

    assert report.chart == STACKED
    assert report.revision == 2
    assert report.updated_by_user_id == OTHER
    assert report.updated_at == later(5)


def test_overwrite_without_a_chart_removes_it() -> None:
    report = make_report(owner=OWNER, chart=BAR)

    report.overwrite(
        make_content(chart=None), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )

    assert report.chart is None


def test_overwrite_clears_the_unreadable_flag() -> None:
    report = make_report(owner=OWNER, chart_unreadable=True)

    report.overwrite(
        make_content(chart=BAR), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )

    assert (report.chart, report.chart_unreadable) == (BAR, False)


def test_overwrite_without_a_chart_also_clears_the_unreadable_flag() -> None:
    report = make_report(owner=OWNER, chart_unreadable=True)

    report.overwrite(
        make_content(), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )

    assert (report.chart, report.chart_unreadable) == (None, False)


def test_a_rejected_overwrite_keeps_the_chart() -> None:
    report = make_report(owner=OWNER, chart=BAR, revision=3)

    from app.domain.saved_report.errors import ReportEditConflictError  # noqa: PLC0415

    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content(chart=STACKED),
            editor=OWNER,
            role=Role.SALES,
            expected_revision=2,
            now=later(1),
        )

    assert (report.chart, report.revision) == (BAR, 3)


def _copy(source: Report, chart: object) -> Report:
    return source.copy_as(
        entity_id=ReportId(new_id()),
        meta_name="복사본",
        meta_description="",
        visibility=ReportVisibility.PUBLIC,
        generated_sql="SELECT 1",
        chart=chart,  # type: ignore[arg-type]
        owner=OTHER,
        now=later(1),
    )


def test_copy_as_uses_the_given_chart() -> None:
    source = make_report(owner=OWNER, chart=BAR)

    copied = _copy(source, STACKED)

    assert copied.chart == STACKED
    assert copied.chart_unreadable is False
    assert source.chart == BAR


def test_copy_as_without_a_chart_has_none() -> None:
    copied = _copy(make_report(owner=OWNER, chart=BAR), None)

    assert copied.chart is None


def test_chart_kind_is_the_kind_of_the_chart() -> None:
    report = make_report(owner=OWNER, chart=STACKED)

    assert report.chart_kind() == ChartKind.STACKED_BAR
    assert report.chart_kind() == "stacked_bar"


def test_chart_kind_is_none_without_a_chart() -> None:
    assert make_report(owner=OWNER).chart_kind() is None


def test_chart_kind_is_none_when_the_stored_chart_is_unreadable() -> None:
    assert make_report(owner=OWNER, chart_unreadable=True).chart_kind() is None
