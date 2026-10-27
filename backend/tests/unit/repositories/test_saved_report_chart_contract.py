"""ReportRepository 차트 계약 (Reports 4단계 AC1·5·7·18): Fake와 SQL 구현 공통 테스트.

차트는 `reports.chart`(JSONB, NULL 가능)에 정규화된 13개 키로 저장된다. 읽을 수 없는 차트는
리포트를 막지 않고 "차트 없음 + 읽을 수 없음"으로 읽힌다(목록·상세·수정·삭제는 계속 된다).
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.report.chart import ChartKind
from app.domain.saved_report.values import ReportListScope
from tests.factories import later
from tests.factories_report import make_content, make_report
from tests.support.chart_defs import chart_definition, raw_chart
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.saved_report_case import SavedReportCase

ALICE = uid("chart-contract-alice")
DEFINITION = chart_definition(2, 3)
FULL = raw_chart(
    "stacked_bar",
    1,
    [2, 4],
    series=0,
    swap=True,
    title="Vendor별 분기 Pipeline",
    legend="bottom",
    data_labels=True,
    category_axis_title="분기",
    value_axis_title="금액 (천원)",
    value_min=-0.5,
    value_max=1000,
    secondary_axis=False,
)
BROKEN_CHART_JSON = ["[1]", '{"kind": "x"}', '{"kind": "bar", "category": "0", "values": [1]}']


def _scope() -> ReportListScope:
    return ReportListScope(viewer_id=ALICE, see_all=True)


async def test_chart_round_trips_with_all_thirteen_keys(saved_report_case: SavedReportCase) -> None:
    report = make_report("차트 왕복", owner=ALICE, definition=DEFINITION, chart=FULL)
    await saved_report_case.add(report)

    stored = await saved_report_case.reports.get(report.id)

    assert stored.chart == FULL
    assert stored.chart_unreadable is False
    assert stored.chart_kind() == ChartKind.STACKED_BAR
    assert stored == report


async def test_none_chart_stays_none(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("차트 없음", owner=ALICE))

    stored = await saved_report_case.reports.get(report.id)

    assert (stored.chart, stored.chart_unreadable, stored.chart_kind()) == (None, False, None)


async def test_chart_defaults_round_trip(saved_report_case: SavedReportCase) -> None:
    chart = raw_chart("pie", 0, [2])
    report = await saved_report_case.add(make_report("기본값", owner=ALICE, chart=chart))

    stored = await saved_report_case.reports.get(report.id)

    assert stored.chart == chart
    assert stored.chart is not None
    assert (stored.chart.legend, stored.chart.value_min, stored.chart.title) == ("top", None, "")


async def test_list_carries_the_chart_of_each_report(saved_report_case: SavedReportCase) -> None:
    with_chart = await saved_report_case.add(
        make_report("차트 있음", owner=ALICE, chart=FULL, updated_at=later(20))
    )
    without = await saved_report_case.add(
        make_report("차트 없음", owner=ALICE, updated_at=later(10))
    )

    listed = await saved_report_case.mine(_scope(), {with_chart.id, without.id})

    assert [(r.name, r.chart_kind()) for r in listed] == [
        ("차트 있음", ChartKind.STACKED_BAR),
        ("차트 없음", None),
    ]


async def test_update_replaces_the_chart(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(
        make_report("교체", owner=ALICE, chart=raw_chart("bar", 0, [2]))
    )
    stored = await saved_report_case.reports.get(report.id)
    stored.overwrite(
        make_content("교체", chart=FULL),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    again = await saved_report_case.reports.get(report.id)
    assert again.chart == FULL
    assert again.revision == 2


async def test_update_clears_the_chart(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("삭제", owner=ALICE, chart=FULL))
    stored = await saved_report_case.reports.get(report.id)
    stored.overwrite(
        make_content("삭제", chart=None),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    again = await saved_report_case.reports.get(report.id)
    assert (again.chart, again.chart_kind()) == (None, None)


async def test_update_without_touching_the_chart_keeps_it(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("유지", owner=ALICE, chart=FULL))
    stored = await saved_report_case.reports.get(report.id)
    stored.overwrite(
        make_content("유지", chart=stored.chart),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    assert (await saved_report_case.reports.get(report.id)).chart == FULL


# ---- 깨진 저장 차트 (AC7) ----


@pytest.mark.parametrize("raw_json", BROKEN_CHART_JSON)
async def test_get_reads_an_unreadable_chart_as_no_chart(
    saved_report_case: SavedReportCase, raw_json: str
) -> None:
    report = await saved_report_case.add(
        make_report("깨진 차트", owner=ALICE, description="설명", chart=FULL)
    )
    await saved_report_case.corrupt_chart(report, raw_json)

    stored = await saved_report_case.reports.get(report.id)

    assert stored.chart is None
    assert stored.chart_unreadable is True
    assert stored.chart_kind() is None
    assert (stored.name, stored.description, stored.revision) == ("깨진 차트", "설명", 1)
    assert stored.definition == report.definition  # 정의는 정상으로 읽힌다


async def test_list_does_not_fail_on_an_unreadable_chart(
    saved_report_case: SavedReportCase,
) -> None:
    healthy = await saved_report_case.add(
        make_report("정상", owner=ALICE, chart=FULL, updated_at=later(10))
    )
    broken = await saved_report_case.add(
        make_report("깨짐", owner=ALICE, chart=FULL, updated_at=later(20))
    )
    await saved_report_case.corrupt_chart(broken, "[1]")

    listed = await saved_report_case.mine(_scope(), {healthy.id, broken.id})

    assert [(r.name, r.chart_kind(), r.chart_unreadable) for r in listed] == [
        ("깨짐", None, True),
        ("정상", ChartKind.STACKED_BAR, False),
    ]


async def test_update_with_a_new_chart_repairs_an_unreadable_one(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("복구 대상", owner=ALICE, chart=FULL))
    await saved_report_case.corrupt_chart(report, '{"kind": "x"}')
    broken = await saved_report_case.reports.get(report.id)
    broken.overwrite(
        make_content("복구 대상", chart=FULL),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(broken)

    stored = await saved_report_case.reports.get(report.id)
    assert (stored.chart, stored.chart_unreadable, stored.revision) == (FULL, False, 2)


async def test_update_without_a_chart_repairs_an_unreadable_one(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("차트 없이 복구", owner=ALICE, chart=FULL))
    await saved_report_case.corrupt_chart(report, "[1]")
    broken = await saved_report_case.reports.get(report.id)
    broken.overwrite(
        make_content("차트 없이 복구", chart=None),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(broken)

    stored = await saved_report_case.reports.get(report.id)
    assert (stored.chart, stored.chart_unreadable) == (None, False)


async def test_delete_removes_a_report_with_an_unreadable_chart(
    saved_report_case: SavedReportCase,
) -> None:
    from app.domain.saved_report.errors import ReportNotFoundError  # noqa: PLC0415

    report = await saved_report_case.add(make_report("깨진 차트 삭제", owner=ALICE, chart=FULL))
    await saved_report_case.corrupt_chart(report, "[1]")

    await saved_report_case.reports.delete(report.id)

    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(report.id)
