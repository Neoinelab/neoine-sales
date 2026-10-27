"""저장 리포트의 차트 유스케이스 (Reports 4단계 AC1·2·4·5·6·7): 저장·검증·덮어쓰기·복제·깨진 차트.

차트는 함께 보낸 정의를 기준으로 검증하고, 위반이면 아무것도 저장하지 않는다(조용히 버리거나
고치지 않는다). 깨진 저장 차트는 목록·상세·실행을 막지 않는다.
"""

from typing import TYPE_CHECKING, Any

import pytest
from app.domain.report.chart import ChartKind

from app.application.report.copy_report import CopyReport
from app.application.report.create_report import CreateReport
from app.application.report.get_report import GetReport
from app.application.report.list_reports import ListReports
from app.application.report.run_saved_report import RunSavedReport
from app.application.report.update_report import UpdateReport
from app.domain.report.errors import ReportDefinitionError
from tests.factories import later
from tests.factories_report import make_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.support.chart_defs import chart_definition, raw_chart
from tests.support.report_defs import col, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    INVALID_DEFINITION,
    content_input,
    meta_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

DEFINITION = chart_definition(2, 3)  # 0·1 = 그룹, 2..4 = 집계 값
UNGROUPED = raw([col("deal.code"), col("deal.amount")])
STACKED = raw_chart("stacked_bar", 0, [2], series=1)


@pytest.fixture
def create(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> CreateReport:
    return CreateReport(uow_factory, clock)


@pytest.fixture
def update(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> UpdateReport:
    clock.advance(600)
    return UpdateReport(uow_factory, clock)


@pytest.fixture
def copy(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> CopyReport:
    return CopyReport(uow_factory, clock)


def _issues(caught: pytest.ExceptionInfo[ReportDefinitionError]) -> list[tuple[Any, str]]:
    return [(tuple(i.location), i.code) for i in caught.value.issues]


# ---- 만들기 (AC1·2) ----


async def test_create_stores_the_normalized_chart(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    chart = raw_chart(
        "stacked_bar", 0, [2], series=1, title="  Vendor별  ", value_axis_title=" 금액"
    )

    report = await create.execute(content_input(definition=DEFINITION, chart=chart), viewer(ALICE))

    expected = raw_chart(
        "stacked_bar",
        0,
        [2],
        series=1,
        title="Vendor별",
        value_axis_title="금액",
        legend="top",
        category_axis_title="",
    )
    assert report.chart == expected
    assert report.chart_unreadable is False
    (saved,) = await stored(uow)
    assert saved.chart == expected
    assert saved.chart_kind() == ChartKind.STACKED_BAR


async def test_create_without_a_chart_has_none(create: CreateReport, uow: FakeUnitOfWork) -> None:
    report = await create.execute(content_input(definition=DEFINITION), viewer(ALICE))

    assert report.chart is None
    (saved,) = await stored(uow)
    assert (saved.chart, saved.chart_kind()) == (None, None)


async def test_invalid_chart_is_not_saved(create: CreateReport, uow: FakeUnitOfWork) -> None:
    chart = raw_chart("bar", 2, [2])  # 범주가 값 컬럼

    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(content_input(definition=DEFINITION, chart=chart), viewer(ALICE))

    assert _issues(caught) == [
        (("chart", "category"), "chart-category-invalid"),
        (("chart", "series"), "chart-series-required"),
    ]
    assert await stored(uow) == []
    assert uow.commits == 0


async def test_chart_issues_are_collected_at_once(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    chart = raw_chart("bar", 9, [0], series=1, legend="left")

    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(content_input(definition=DEFINITION, chart=chart), viewer(ALICE))

    assert {code for _, code in _issues(caught)} == {
        "chart-category-invalid",
        "chart-value-invalid",
        "chart-legend-invalid",
    }
    assert await stored(uow) == []


async def test_chart_for_an_ungrouped_definition_is_rejected(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(content_input(definition=UNGROUPED, chart=raw_chart()), viewer(ALICE))

    assert _issues(caught) == [(("chart",), "chart-needs-grouping")]
    assert await stored(uow) == []


async def test_definition_issues_win_over_chart_issues(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    chart = raw_chart("nope", 99, "garbage")

    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(
            content_input(definition=INVALID_DEFINITION, chart=chart), viewer(ALICE)
        )

    locations = [location for location, _ in _issues(caught)]
    assert locations == [("columns", 0, "field")]
    assert all(location[0] != "chart" for location in locations)
    assert await stored(uow) == []


async def test_name_issue_comes_before_the_chart_check(create: CreateReport) -> None:
    with pytest.raises(ValueError, match="이름") as caught:
        await create.execute(
            content_input("", definition=DEFINITION, chart=raw_chart("nope", 99, "x")),
            viewer(ALICE),
        )

    assert not isinstance(caught.value, ReportDefinitionError)


# ---- 덮어쓰기 (AC4·5) ----


async def test_update_replaces_or_clears_the_chart_and_bumps_revision(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, definition=DEFINITION, chart=raw_chart("bar", 0, [2]))
    await seed(uow, report)

    changed = await update.execute(
        report.id, content_input("원본", definition=DEFINITION, chart=STACKED), 1, viewer(ALICE)
    )
    cleared = await update.execute(
        report.id, content_input("원본", definition=DEFINITION, chart=None), 2, viewer(ALICE)
    )

    assert changed.chart == raw_chart("stacked_bar", 0, [2], series=1)
    assert changed.revision == 2  # 차트만 바꿔도 revision이 오른다
    assert changed.updated_by_user_id == ALICE
    assert changed.updated_at == later(600)
    assert changed.generated_sql == RENDERED_SQL  # 차트와 무관
    assert cleared.chart is None
    assert cleared.revision == 3
    (saved,) = await stored(uow)
    assert (saved.chart, saved.revision) == (None, 3)


async def test_update_with_chart_invalid_for_the_new_definition_is_rejected(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    old_chart = raw_chart("stacked_bar", 0, [2], series=1)
    report = make_report("원본", owner=ALICE, definition=DEFINITION, chart=old_chart)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:  # 그룹핑을 끈 정의 + 이전 차트
        await update.execute(
            report.id,
            content_input("원본", definition=UNGROUPED, chart=old_chart),
            1,
            viewer(ALICE),
        )

    assert _issues(caught) == [(("chart",), "chart-needs-grouping")]
    (saved,) = await stored(uow)
    assert (saved.definition, saved.chart, saved.revision) == (DEFINITION, old_chart, 1)
    assert uow.commits == 0


async def test_update_with_a_value_column_removed_rejects_the_chart_index(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, definition=DEFINITION, chart=raw_chart("bar", 0, [4]))
    await seed(uow, report)
    narrower = chart_definition(2, 1)  # 값 컬럼이 index 2 하나뿐

    with pytest.raises(ReportDefinitionError) as caught:
        await update.execute(
            report.id,
            content_input("원본", definition=narrower, chart=raw_chart("bar", 0, [4], series=1)),
            1,
            viewer(ALICE),
        )

    assert _issues(caught) == [(("chart", "values", 0), "chart-value-invalid")]


async def test_update_without_a_chart_removes_the_stored_one(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, definition=DEFINITION, chart=STACKED)
    await seed(uow, report)

    result = await update.execute(
        report.id, content_input("원본", definition=DEFINITION), 1, viewer(ALICE)
    )

    assert result.chart is None


async def test_update_repairs_an_unreadable_chart(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("깨진 차트", owner=ALICE, definition=DEFINITION, chart_unreadable=True)
    await seed(uow, report)

    result = await update.execute(
        report.id,
        content_input("깨진 차트", definition=DEFINITION, chart=STACKED),
        1,
        viewer(ALICE),
    )

    assert (result.chart is not None, result.chart_unreadable) == (True, False)
    (saved,) = await stored(uow)
    assert (saved.chart_unreadable, saved.chart_kind()) == (False, ChartKind.STACKED_BAR)


# ---- 복제 (AC6) ----


async def test_copy_carries_the_chart_of_the_source(copy: CopyReport, uow: FakeUnitOfWork) -> None:
    chart = raw_chart("stacked_bar", 0, [2], series=1, title="제목", legend="bottom")
    source = make_report("원본", owner=ALICE, definition=DEFINITION, chart=chart)
    await seed(uow, source)

    result = await copy.execute(source.id, meta_input("복사본"), viewer(ALICE))

    assert result.chart == chart
    assert result.chart_unreadable is False
    saved = next(r for r in await stored(uow) if r.id == result.id)
    assert saved.chart == chart
    original = next(r for r in await stored(uow) if r.id == source.id)
    assert original.chart == chart


async def test_copy_of_a_report_without_a_chart_has_none(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    source = make_report("원본", owner=ALICE, definition=DEFINITION)
    await seed(uow, source)

    result = await copy.execute(source.id, meta_input("복사본"), viewer(ALICE))

    assert result.chart is None


async def test_copy_drops_an_unreadable_chart_and_succeeds(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    source = make_report("원본", owner=ALICE, definition=DEFINITION, chart_unreadable=True)
    await seed(uow, source)

    result = await copy.execute(source.id, meta_input("복사본"), viewer(ALICE))

    assert (result.chart, result.chart_unreadable) == (None, False)
    assert len(await stored(uow)) == 2


async def test_copy_with_chart_invalid_for_current_rules_is_rejected(
    copy: CopyReport, uow: FakeUnitOfWork
) -> None:
    broken_chart = raw_chart(
        "bar", 2, [2], series=1
    )  # 범주가 값 컬럼(저장소에 직접 넣은 낡은 차트)
    source = make_report("원본", owner=ALICE, definition=DEFINITION, chart=broken_chart)
    await seed(uow, source)

    with pytest.raises(ReportDefinitionError) as caught:
        await copy.execute(source.id, meta_input("복사본"), viewer(ALICE))

    assert _issues(caught) == [(("chart", "category"), "chart-category-invalid")]
    assert len(await stored(uow)) == 1


# ---- 깨진 저장 차트 (AC7) ----


async def test_get_list_and_run_do_not_fail_on_an_unreadable_chart(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    broken = make_report("깨진 차트", owner=ALICE, definition=DEFINITION, chart_unreadable=True)
    healthy = make_report("정상", owner=ALICE, definition=DEFINITION)
    await seed(uow, broken, healthy)

    got = await GetReport(uow_factory).execute(broken.id, viewer(ALICE))
    listed = await ListReports(uow_factory).execute(viewer(ALICE))
    run_broken = await RunSavedReport(uow_factory, clock).execute(broken.id, viewer(ALICE))
    run_healthy = await RunSavedReport(uow_factory, clock).execute(healthy.id, viewer(ALICE))

    assert (got.chart, got.chart_unreadable) == (None, True)
    by_name = {i.report.name: i.report for i in listed}
    assert by_name["깨진 차트"].chart_kind() is None
    assert by_name["정상"].chart_kind() is None
    assert run_broken == run_healthy


async def test_list_shows_the_chart_kind_of_each_report(
    uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    with_chart = make_report("차트 있음", owner=ALICE, definition=DEFINITION, chart=STACKED)
    without = make_report("차트 없음", owner=ALICE, definition=DEFINITION)
    await seed(uow, with_chart, without)

    listed = await ListReports(uow_factory).execute(viewer(ALICE))

    kinds = {i.report.name: i.report.chart_kind() for i in listed}
    assert kinds == {"차트 있음": ChartKind.STACKED_BAR, "차트 없음": None}
