"""저장 리포트의 결과 배치 유스케이스 (AC22~28): 저장·유지·복제·배치만 바꾸기와 판정 순서.

배치는 정의·차트 검증 뒤에 검사한다(정의 위반이 있으면 배치는 검사하지 않는다). 배치만 바꾸기는
행 잠금 뒤 404 -> 422 -> 403 -> 409 순으로 판정하고, 정의·차트는 건드리지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.report.change_report_layout import ChangeReportLayout
from app.application.report.copy_report import CopyReport
from app.application.report.create_report import CreateReport
from app.application.report.update_report import UpdateReport
from app.domain.auth.principal import Role
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report import entities
from app.domain.saved_report.errors import (
    ReportEditConflictError,
    ReportEditForbiddenError,
    ReportNotFoundError,
)
from app.domain.saved_report.layout import DEFAULT_LAYOUT
from app.domain.saved_report.values import ReportId
from tests.factories import later
from tests.factories_report import make_broken_report, make_report
from tests.support.chart_defs import chart_definition, raw_chart
from tests.support.ids import MISSING_ID
from tests.support.layout_defs import make_layout, raw_layout
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
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

SIDE = make_layout("chart", ("chart", "table"), "side_by_side")
SIDE_RAW = raw_layout("chart", ("chart", "table"), "side_by_side")
TABLE = make_layout("table", ("table", "chart"), "stacked")
TABLE_RAW = raw_layout("table", ("table", "chart"), "stacked")


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


@pytest.fixture
def change(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> ChangeReportLayout:
    clock.advance(600)
    return ChangeReportLayout(uow_factory, clock)


# ---- 만들기·덮어쓰기·복제 (AC24, 28) ----


async def test_create_report_stores_given_layout(create: CreateReport, uow: FakeUnitOfWork) -> None:
    report = await create.execute(content_input(layout=SIDE_RAW), viewer(ALICE))

    assert report.layout == SIDE
    (saved,) = await stored(uow)
    assert saved.layout == SIDE


async def test_create_report_without_layout_stores_default(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    report = await create.execute(content_input(), viewer(ALICE))

    assert report.layout == DEFAULT_LAYOUT
    (saved,) = await stored(uow)
    assert saved.layout == DEFAULT_LAYOUT


async def test_create_report_with_invalid_layout_saves_nothing(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(content_input(layout=raw_layout(view="grid")), viewer(ALICE))

    assert [tuple(i.location) for i in caught.value.issues] == [("layout", "view")]
    assert await stored(uow) == []
    assert uow.commits == 0


async def test_update_report_with_layout_replaces_it(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)

    result = await update.execute(
        report.id, content_input("원본", layout=TABLE_RAW), 1, viewer(ALICE)
    )

    assert result.layout == TABLE
    (saved,) = await stored(uow)
    assert saved.layout == TABLE


async def test_update_report_omitted_layout_keeps_previous(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)

    result = await update.execute(report.id, content_input("새 이름"), 1, viewer(ALICE))

    assert result.layout == SIDE
    (saved,) = await stored(uow)
    assert (saved.name, saved.layout, saved.revision) == ("새 이름", SIDE, 2)


async def test_update_report_invalid_definition_skips_layout_check(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)
    both_bad = content_input(
        definition=INVALID_DEFINITION, layout=raw_layout(view="x", order=["a"], arrange="y")
    )

    with pytest.raises(ReportDefinitionError) as caught:
        await update.execute(report.id, both_bad, 1, viewer(ALICE))

    locations = [tuple(i.location) for i in caught.value.issues]
    assert locations
    assert all(loc[0] != "layout" for loc in locations)
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (SIDE, 1)


async def test_update_report_invalid_layout_keeps_stored_report(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await update.execute(
            report.id, content_input("바뀜", layout=raw_layout(arrange="row")), 1, viewer(ALICE)
        )

    assert [tuple(i.location) for i in caught.value.issues] == [("layout", "arrange")]
    (saved,) = await stored(uow)
    assert (saved.name, saved.layout, saved.revision) == ("원본", SIDE, 1)


async def test_chart_issues_come_before_layout_issues(create: CreateReport) -> None:
    chart = raw_chart("bar", 9, [0])

    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(
            content_input(
                definition=chart_definition(2, 3), chart=chart, layout=raw_layout(view="x")
            ),
            viewer(ALICE),
        )

    assert all(i.location[0] != "layout" for i in caught.value.issues)


async def test_copy_report_copies_source_layout(copy: CopyReport, uow: FakeUnitOfWork) -> None:
    source = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, source)

    result = await copy.execute(source.id, meta_input("복사본"), viewer(BOB))

    assert result.layout == SIDE
    saved = {r.name: r.layout for r in await stored(uow)}
    assert saved == {"원본": SIDE, "복사본": SIDE}


# ---- 배치만 바꾸기 (AC22, 26) ----


async def test_change_report_layout_success_returns_updated_report(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    chart = raw_chart("bar", 0, [1])
    definition = chart_definition(1, 3)
    report = make_report(
        "원본", owner=ALICE, visibility="public", definition=definition, chart=chart, revision=2
    )
    await seed(uow, report)

    result = await change.execute(report.id, SIDE_RAW, 2, viewer(BOB))

    assert result.layout == SIDE
    assert result.revision == 3
    assert result.updated_by_user_id == BOB
    assert result.updated_at == later(600)
    assert (result.name, result.definition, result.chart) == ("원본", definition, chart)
    assert result.owner_user_id == ALICE
    assert uow.commits == 1
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision, saved.updated_by_user_id) == (SIDE, 3, BOB)
    assert (saved.definition, saved.chart, saved.generated_sql) == (
        definition,
        chart,
        report.generated_sql,
    )


async def test_change_report_layout_keeps_an_unreadable_stored_chart(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_report("깨진 차트", owner=ALICE, chart_unreadable=True)
    await seed(uow, report)

    result = await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))

    assert result.layout == SIDE
    (saved,) = await stored(uow)
    assert saved.chart is None
    assert saved.chart_unreadable is True
    assert saved.layout == SIDE


async def test_change_report_layout_consecutive_calls_with_returned_revision_succeed(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)

    first = await change.execute(report.id, SIDE_RAW, report.revision, viewer(ALICE))
    second = await change.execute(report.id, TABLE_RAW, first.revision, viewer(ALICE))

    assert (first.revision, second.revision) == (2, 3)
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (TABLE, 3)


async def test_change_report_layout_with_the_old_revision_after_a_save_conflicts(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)
    await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))

    with pytest.raises(ReportEditConflictError):
        await change.execute(report.id, TABLE_RAW, 1, viewer(ALICE))

    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (SIDE, 2)


async def test_change_report_layout_rejects_an_invalid_layout_without_saving(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await change.execute(report.id, raw_layout(order=["table", "table"]), 1, viewer(ALICE))

    assert [tuple(i.location) for i in caught.value.issues] == [("layout", "order")]
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (SIDE, 1)
    assert uow.commits == 0


async def test_change_report_layout_checks_not_found_before_invalid_layout(
    change: ChangeReportLayout,
) -> None:
    with pytest.raises(ReportNotFoundError):
        await change.execute(ReportId(MISSING_ID), raw_layout(view="x"), 1, viewer(ALICE))


async def test_change_report_layout_of_others_private_report_is_not_found(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)

    for role in (Role.SALES, Role.USER):
        with pytest.raises(ReportNotFoundError):
            await change.execute(report.id, SIDE_RAW, 1, viewer(BOB, role))

    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (DEFAULT_LAYOUT, 1)


async def test_change_report_layout_checks_hidden_before_invalid_layout(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)

    with pytest.raises(ReportNotFoundError):
        await change.execute(report.id, raw_layout(view="x"), 1, viewer(BOB))


async def test_change_report_layout_checks_invalid_layout_before_forbidden(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError):
        await change.execute(report.id, raw_layout(view="x"), 1, viewer(BOB))


async def test_change_report_layout_without_edit_right_is_forbidden(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)

    with pytest.raises(ReportEditForbiddenError):
        await change.execute(report.id, SIDE_RAW, 1, viewer(BOB))

    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (DEFAULT_LAYOUT, 1)


async def test_change_report_layout_checks_forbidden_before_conflict(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report("원본", owner=ALICE, revision=4)
    await seed(uow, report)

    with pytest.raises(ReportEditForbiddenError):
        await change.execute(report.id, SIDE_RAW, 1, viewer(BOB))


async def test_change_report_layout_with_a_stale_revision_conflicts(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_report("원본", owner=ALICE, revision=4)
    await seed(uow, report)

    with pytest.raises(ReportEditConflictError):
        await change.execute(report.id, SIDE_RAW, 3, viewer(ALICE))

    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (DEFAULT_LAYOUT, 4)
    assert uow.commits == 0


# ---- 깨진 저장 정의: 부수 효과 없이 stored-invalid (판정 순서 404, 깨진 정의, 배치, 403, 409) ----

STORED_INVALID = [(("definition",), "stored-invalid")]


def _issues(caught: pytest.ExceptionInfo[ReportDefinitionError]) -> list[tuple[object, str]]:
    return [(i.location, i.code) for i in caught.value.issues]


async def _assert_untouched(uow: FakeUnitOfWork, revision: int = 1) -> None:
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision, saved.updated_by_user_id) == (
        DEFAULT_LAYOUT,
        revision,
        ALICE,
    )
    assert saved.definition is None
    assert uow.commits == 0


async def test_change_report_layout_of_a_broken_definition_is_stored_invalid_without_side_effects(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_broken_report(owner=ALICE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))

    assert _issues(caught) == STORED_INVALID
    await _assert_untouched(uow)


async def test_change_report_layout_checks_a_broken_definition_before_the_layout_value(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_broken_report(owner=ALICE)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as caught:
        await change.execute(report.id, raw_layout(view="x"), 1, viewer(ALICE))

    assert _issues(caught) == STORED_INVALID
    await _assert_untouched(uow)


async def test_change_report_layout_checks_a_broken_definition_before_forbidden_and_conflict(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = make_broken_report(owner=ALICE, revision=4)
    await seed(uow, report)

    with pytest.raises(ReportDefinitionError) as stale:
        await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    with pytest.raises(ReportDefinitionError) as forbidden:
        await change.execute(report.id, SIDE_RAW, 4, viewer(BOB))

    assert _issues(stale) == _issues(forbidden) == STORED_INVALID
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (DEFAULT_LAYOUT, 4)
    assert uow.commits == 0


async def test_change_report_layout_of_others_private_broken_report_is_not_found(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    report = make_broken_report(owner=ALICE, visibility="private")
    await seed(uow, report)

    with pytest.raises(ReportNotFoundError):
        await change.execute(report.id, SIDE_RAW, 1, viewer(BOB))

    await _assert_untouched(uow)
