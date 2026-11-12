"""Report 엔티티와 차트: 만들기·덮어쓰기·복제와 목록용 종류(RC-R18~RC-R20)."""

import pytest

from app.domain.auth.principal import Role
from app.domain.report.chart_kinds import ChartKind
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
    """새 리포트는 기본으로 차트가 없고 읽을 수 없음 표시도 없다."""
    # when: 내용에 차트가 없는 리포트를 만든다
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(), owner=OWNER, now=NOW
    )

    # then: 차트는 None이고 읽을 수 없음 표시가 꺼져 있다
    assert report.chart is None
    assert report.chart_unreadable is False


def test_create_keeps_the_chart_of_the_content() -> None:
    """새 리포트는 내용에 담긴 차트를 그대로 가진다."""
    # when: 차트가 있는 내용으로 리포트를 만든다
    report = Report.create(
        entity_id=ReportId(new_id()), content=make_content(chart=BAR), owner=OWNER, now=NOW
    )

    # then: 차트가 내용의 차트와 같다
    assert report.chart == BAR
    assert report.chart_unreadable is False


def test_overwrite_replaces_the_chart_and_bumps_the_revision() -> None:
    """덮어쓰기는 차트를 바꾸고 revision과 수정자·시각을 갱신한다."""
    # given: 차트가 있는 공개 리포트
    report = make_report(owner=OWNER, visibility="public", chart=BAR)

    # when: 다른 차트로 덮어쓴다
    report.overwrite(
        make_content(chart=STACKED),
        editor=OTHER,
        role=Role.SALES,
        expected_revision=1,
        now=later(5),
    )

    # then: 차트가 새 차트이고 revision 2, 수정자와 수정 시각이 갱신된다
    assert report.chart == STACKED
    assert report.revision == 2
    assert report.updated_by_user_id == OTHER
    assert report.updated_at == later(5)


def test_overwrite_without_a_chart_removes_it() -> None:
    """차트 없이 덮어쓰면 저장된 차트가 지워진다."""
    # given: 차트가 있는 리포트
    report = make_report(owner=OWNER, chart=BAR)

    # when: 차트 없는 내용으로 덮어쓴다
    report.overwrite(
        make_content(chart=None), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )

    # then: 차트가 None이다
    assert report.chart is None


def test_overwrite_clears_the_unreadable_flag() -> None:
    """차트를 읽을 수 없던 리포트를 새 차트로 덮어쓰면 읽을 수 없음 표시가 지워진다.

    테스트 코드: RC-041
    """
    # given: 저장 차트를 읽을 수 없는 리포트
    report = make_report(owner=OWNER, chart_unreadable=True)

    # when: 새 차트로 덮어쓴다
    report.overwrite(
        make_content(chart=BAR), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )

    # then: 새 차트가 있고 읽을 수 없음 표시가 꺼진다
    assert (report.chart, report.chart_unreadable) == (BAR, False)


def test_overwrite_without_a_chart_also_clears_the_unreadable_flag() -> None:
    """차트 없이 덮어써도 읽을 수 없음 표시가 지워진다.

    테스트 코드: RC-041
    """
    # given: 저장 차트를 읽을 수 없는 리포트
    report = make_report(owner=OWNER, chart_unreadable=True)

    # when: 차트 없는 내용으로 덮어쓴다
    report.overwrite(
        make_content(), editor=OWNER, role=Role.SALES, expected_revision=1, now=later(1)
    )

    # then: 차트는 None이고 읽을 수 없음 표시가 꺼진다
    assert (report.chart, report.chart_unreadable) == (None, False)


def test_a_rejected_overwrite_keeps_the_chart() -> None:
    """거절된 덮어쓰기는 차트와 revision을 바꾸지 않는다."""
    # given: revision 3에 차트가 있는 리포트
    report = make_report(owner=OWNER, chart=BAR, revision=3)

    from app.domain.saved_report.errors import ReportEditConflictError  # noqa: PLC0415

    # when·then: 오래된 revision(2)으로 덮어쓰면 충돌 오류가 난다
    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content(chart=STACKED),
            editor=OWNER,
            role=Role.SALES,
            expected_revision=2,
            now=later(1),
        )

    # then: 차트와 revision이 그대로다
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
    """복사본은 넘겨받은 차트를 가지고 원본 차트는 그대로다."""
    # given: 차트가 있는 원본 리포트
    source = make_report(owner=OWNER, chart=BAR)

    # when: 다른 차트를 넘겨 복사한다
    copied = _copy(source, STACKED)

    # then: 복사본은 넘긴 차트이고 읽을 수 없음 표시가 꺼져 있으며 원본은 그대로다
    assert copied.chart == STACKED
    assert copied.chart_unreadable is False
    assert source.chart == BAR


def test_copy_as_without_a_chart_has_none() -> None:
    """차트 없이 복사하면 복사본에 차트가 없다."""
    # when: 차트 없음을 넘겨 복사한다 (전제: 원본에는 차트가 있다)
    copied = _copy(make_report(owner=OWNER, chart=BAR), None)

    # then: 복사본 차트가 None이다
    assert copied.chart is None


def test_chart_kind_is_the_kind_of_the_chart() -> None:
    """차트 종류는 저장 차트의 종류다.

    테스트 코드: RC-037
    """
    # given: 누적 막대 차트가 있는 리포트
    report = make_report(owner=OWNER, chart=STACKED)

    # when: 차트 종류를 읽는다
    kind = report.chart_kind()

    # then: stacked_bar다
    assert kind == ChartKind.STACKED_BAR
    assert str(kind.value) == "stacked_bar"


def test_chart_kind_is_none_without_a_chart() -> None:
    """차트가 없으면 차트 종류는 None이다.

    테스트 코드: RC-037
    """
    # given: 차트 없는 리포트
    report = make_report(owner=OWNER)

    # when: 차트 종류를 읽는다
    kind = report.chart_kind()
    # then: None이다
    assert kind is None


def test_chart_kind_is_none_when_the_stored_chart_is_unreadable() -> None:
    """저장 차트를 읽을 수 없으면 차트 종류는 None이다.

    테스트 코드: RC-037, RC-040
    """
    # given: 저장 차트를 읽을 수 없는 리포트
    report = make_report(owner=OWNER, chart_unreadable=True)

    # when: 차트 종류를 읽는다
    kind = report.chart_kind()
    # then: None이다
    assert kind is None


@pytest.mark.parametrize(
    ("kind", "category", "values"),
    [
        ("treemap", 0, [1]),
        ("histogram", None, [1]),
        ("bubble", 0, [1, 2, 3]),
        ("waterfall", 0, [1]),
    ],
)
def test_chart_kind_returns_new_kinds(kind: str, category: int | None, values: list[int]) -> None:
    """새 종류(트리맵·히스토그램·거품형·폭포)도 차트 종류로 돌려준다.

    테스트 코드: RC-037
    """
    # given: 새 종류 차트가 있는 리포트
    report = make_report(owner=OWNER, chart=raw_chart(kind, category, values))

    # when: 차트 종류를 읽는다
    actual = report.chart_kind()

    # then: 저장한 종류와 같다
    assert actual == ChartKind(kind)
    assert actual == kind
