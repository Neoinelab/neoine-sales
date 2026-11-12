"""저장 리포트의 결과 배치 유스케이스: 저장·유지·복제·배치만 바꾸기와 판정 순서.

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
    ROOT,
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


# ---- 만들기·덮어쓰기·복제 ----


async def test_create_report_stores_given_layout(create: CreateReport, uow: FakeUnitOfWork) -> None:
    """배치를 정해 만들면 같은 배치로 저장된다.

    테스트 코드: RS-038
    """
    # when: CHART_SIDE 배치로 만든다
    report = await create.execute(content_input(layout=SIDE_RAW), viewer(ALICE))
    # then: 응답과 저장소의 배치가 CHART_SIDE이고 revision 1이다
    assert report.layout == SIDE
    assert report.revision == 1
    (saved,) = await stored(uow)
    assert saved.layout == SIDE


async def test_create_report_without_layout_stores_default(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """배치 없이 만들면 기본 배치로 저장된다.

    테스트 코드: RS-038
    """
    # when: layout 없이 만든다
    report = await create.execute(content_input(), viewer(ALICE))
    # then: 응답과 저장소의 배치가 기본 배치다
    assert report.layout == DEFAULT_LAYOUT
    (saved,) = await stored(uow)
    assert saved.layout == DEFAULT_LAYOUT


async def test_create_report_with_invalid_layout_saves_nothing(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """배치 값이 틀리면 만들기는 layout 위치 위반이고 저장되지 않는다.

    테스트 코드: RS-044
    """
    # when·then: view가 "grid"인 배치로 만들면 ["layout","view"] 위반이다
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(content_input(layout=raw_layout(view="grid")), viewer(ALICE))
    assert [tuple(i.location) for i in caught.value.issues] == [("layout", "view")]
    # then: 저장되지 않는다
    assert await stored(uow) == []
    assert uow.commits == 0


async def test_update_report_with_layout_replaces_it(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """배치를 보내 덮어쓰면 배치가 바뀌고 revision이 오른다.

    테스트 코드: RS-040
    """
    # given: 배치 CHART_SIDE인 리포트
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)
    # when: TABLE_ONLY 배치를 보내 덮어쓴다
    result = await update.execute(
        report.id, content_input("원본", layout=TABLE_RAW), 1, viewer(ALICE)
    )
    # then: 배치가 TABLE_ONLY이고 revision 2다
    assert (result.layout, result.revision) == (TABLE, 2)
    (saved,) = await stored(uow)
    assert saved.layout == TABLE


async def test_update_report_omitted_layout_keeps_previous(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """배치 없이 덮어쓰면 저장된 배치가 남는다.

    테스트 코드: RS-040
    """
    # given: 배치 CHART_SIDE인 리포트
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)
    # when: layout 없이 이름만 바꿔 덮어쓴다
    result = await update.execute(report.id, content_input("새 이름"), 1, viewer(ALICE))
    # then: 이름은 바뀌고 배치는 CHART_SIDE 그대로, revision 2다
    assert result.layout == SIDE
    (saved,) = await stored(uow)
    assert (saved.name, saved.layout, saved.revision) == ("새 이름", SIDE, 2)


async def test_update_report_invalid_definition_skips_layout_check(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """정의 위반이 있는 덮어쓰기는 틀린 배치를 검사하지 않고 저장도 바뀌지 않는다.

    테스트 코드: RS-007
    """
    # given: 배치 CHART_SIDE인 리포트와 틀린 정의·틀린 배치
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)
    both_bad = content_input(
        definition=INVALID_DEFINITION, layout=raw_layout(view="x", order=["a"], arrange="y")
    )
    # when·then: 덮어쓰면 정의 위치 위반만 있다
    with pytest.raises(ReportDefinitionError) as caught:
        await update.execute(report.id, both_bad, 1, viewer(ALICE))
    locations = [tuple(i.location) for i in caught.value.issues]
    assert locations
    assert all(loc[0] != "layout" for loc in locations)
    # then: 저장된 배치·revision이 그대로다
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (SIDE, 1)


async def test_update_report_invalid_layout_keeps_stored_report(
    update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """배치 값이 틀린 덮어쓰기는 layout 위치 위반이고 저장된 리포트는 그대로다.

    테스트 코드: RS-044
    """
    # given: 배치 CHART_SIDE인 리포트
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)
    # when·then: arrange가 "row"인 배치로 덮어쓰면 ["layout","arrange"] 위반이다
    with pytest.raises(ReportDefinitionError) as caught:
        await update.execute(
            report.id, content_input("바뀜", layout=raw_layout(arrange="row")), 1, viewer(ALICE)
        )
    assert [tuple(i.location) for i in caught.value.issues] == [("layout", "arrange")]
    # then: 이름·배치·revision이 그대로다
    (saved,) = await stored(uow)
    assert (saved.name, saved.layout, saved.revision) == ("원본", SIDE, 1)


async def test_chart_issues_come_before_layout_issues(create: CreateReport) -> None:
    """차트 위반이 있으면 틀린 배치는 검사하지 않는다.

    테스트 코드: RS-007
    """
    # given: 정의에 맞지 않는 차트와 틀린 배치
    chart = raw_chart("bar", 9, [0])
    # when·then: 만들면 위반 위치에 layout이 없다
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(
            content_input(
                definition=chart_definition(2, 3), chart=chart, layout=raw_layout(view="x")
            ),
            viewer(ALICE),
        )
    assert all(i.location[0] != "layout" for i in caught.value.issues)


async def test_copy_report_copies_source_layout(copy: CopyReport, uow: FakeUnitOfWork) -> None:
    """복제하면 원본의 배치를 그대로 가져가고 원본 배치는 그대로다.

    테스트 코드: RS-028
    """
    # given: 배치 CHART_SIDE인 원본
    source = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, source)
    # when: BOB이 복제한다
    result = await copy.execute(source.id, meta_input("복사본"), viewer(BOB))
    # then: 복제본과 원본 모두 CHART_SIDE다
    assert result.layout == SIDE
    saved = {r.name: r.layout for r in await stored(uow)}
    assert saved == {"원본": SIDE, "복사본": SIDE}


# ---- 배치만 바꾸기 ----


async def test_change_report_layout_success_returns_updated_report(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """배치만 저장하면 배치·수정자·시각·revision만 바뀌고 정의·차트·이름은 그대로다.

    테스트 코드: RS-041, RS-043
    """
    # given: 차트가 있는 ALICE의 공개 리포트(revision 2)
    chart = raw_chart("bar", 0, [1])
    definition = chart_definition(1, 3)
    report = make_report(
        "원본", owner=ALICE, visibility="public", definition=definition, chart=chart, revision=2
    )
    await seed(uow, report)
    # when: BOB이 CHART_SIDE 배치를 revision 2로 저장한다
    result = await change.execute(report.id, SIDE_RAW, 2, viewer(BOB))
    # then: 배치·revision·최종 수정자·수정 시각만 바뀐다
    assert result.layout == SIDE
    assert result.revision == 3
    assert result.updated_by_user_id == BOB
    assert result.updated_at == later(600)
    assert (result.name, result.definition, result.chart) == ("원본", definition, chart)
    assert result.owner_user_id == ALICE
    assert uow.commits == 1
    # then: 저장소에도 정의·차트·SQL은 그대로다
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
    """읽을 수 없는 저장 차트가 있는 리포트의 배치 저장은 차트 상태를 그대로 둔다.

    테스트 코드: RS-041
    """
    # given: 저장 차트를 읽을 수 없는 리포트
    report = make_report("깨진 차트", owner=ALICE, chart_unreadable=True)
    await seed(uow, report)
    # when: 배치를 저장한다
    result = await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))
    # then: 배치만 바뀌고 차트 없음·읽을 수 없음 상태는 그대로다
    assert result.layout == SIDE
    (saved,) = await stored(uow)
    assert saved.chart is None
    assert saved.chart_unreadable is True
    assert saved.layout == SIDE


async def test_change_report_layout_consecutive_calls_with_returned_revision_succeed(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """응답 revision으로 배치를 이어 저장하면 모두 된다.

    테스트 코드: RS-042
    """
    # given: revision 1인 리포트
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)
    # when: 직전 응답의 revision으로 두 번 저장한다
    first = await change.execute(report.id, SIDE_RAW, report.revision, viewer(ALICE))
    second = await change.execute(report.id, TABLE_RAW, first.revision, viewer(ALICE))
    # then: revision이 2, 3이고 마지막 배치가 저장된다
    assert (first.revision, second.revision) == (2, 3)
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (TABLE, 3)


async def test_change_report_layout_with_the_old_revision_after_a_save_conflicts(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """낡은 revision으로 배치를 저장하면 충돌이고 배치는 그대로다.

    테스트 코드: RS-042
    """
    # given: revision 1로 한 번 저장해 revision 2가 된 리포트
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)
    await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))
    # when·then: revision 1로 다시 저장하면 충돌이다
    with pytest.raises(ReportEditConflictError):
        await change.execute(report.id, TABLE_RAW, 1, viewer(ALICE))
    # then: 배치와 revision이 그대로다
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (SIDE, 2)


async def test_change_report_layout_after_someone_else_overwrote_conflicts(
    change: ChangeReportLayout, update: UpdateReport, uow: FakeUnitOfWork
) -> None:
    """다른 사람이 먼저 덮어쓴 뒤 이전 revision으로 배치를 저장하면 충돌이다.

    테스트 코드: RS-042
    """
    # given: BOB이 revision 1로 덮어써 revision 2가 된 공개 리포트
    report = make_report("원본", owner=ALICE, visibility="public")
    await seed(uow, report)
    await update.execute(report.id, content_input("BOB 수정"), 1, viewer(BOB))
    # when·then: ALICE가 revision 1로 배치를 저장하면 충돌이다
    with pytest.raises(ReportEditConflictError):
        await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))
    # then: BOB이 저장한 값 그대로다
    (saved,) = await stored(uow)
    assert (saved.name, saved.layout, saved.revision) == ("BOB 수정", DEFAULT_LAYOUT, 2)


async def test_change_report_layout_rejects_an_invalid_layout_without_saving(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """배치 값이 틀리면 배치 저장은 layout 위치 위반이고 저장되지 않는다.

    테스트 코드: RS-044
    """
    # given: 배치 CHART_SIDE인 리포트
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)
    # when·then: order가 ["table","table"]이면 ["layout","order"] 위반이다
    with pytest.raises(ReportDefinitionError) as caught:
        await change.execute(report.id, raw_layout(order=["table", "table"]), 1, viewer(ALICE))
    assert [tuple(i.location) for i in caught.value.issues] == [("layout", "order")]
    # then: 배치·revision이 그대로이고 커밋이 없다
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (SIDE, 1)
    assert uow.commits == 0


@pytest.mark.parametrize(
    ("layout", "locations"),
    [
        (raw_layout(view="grid"), [("layout", "view")]),
        (raw_layout(arrange="row"), [("layout", "arrange")]),
        (
            raw_layout(view="x", order=["a"], arrange="y"),
            [("layout", "view"), ("layout", "order"), ("layout", "arrange")],
        ),
    ],
    ids=["view", "arrange", "all-three"],
)
async def test_change_report_layout_reports_every_wrong_value_location(
    change: ChangeReportLayout, uow: FakeUnitOfWork, layout: object, locations: list[object]
) -> None:
    """배치 저장은 틀린 값의 위치를 모두 알리고 저장하지 않는다.

    테스트 코드: RS-044
    """
    # given: 배치 CHART_SIDE인 리포트
    report = make_report("원본", owner=ALICE, layout=SIDE)
    await seed(uow, report)
    # when·then: 틀린 배치를 저장하면 틀린 위치가 모두 위반으로 나온다
    with pytest.raises(ReportDefinitionError) as caught:
        await change.execute(report.id, layout, 1, viewer(ALICE))  # type: ignore[arg-type]
    assert [tuple(i.location) for i in caught.value.issues] == locations
    assert {i.code for i in caught.value.issues} == {"invalid-value"}
    # then: 배치가 바뀌지 않는다
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (SIDE, 1)


async def test_change_report_layout_checks_not_found_before_invalid_layout(
    change: ChangeReportLayout,
) -> None:
    """없는 리포트의 배치 저장은 틀린 배치여도 404가 먼저다.

    테스트 코드: RS-046
    """
    # when·then: 없는 id에 틀린 배치를 보내면 404다
    with pytest.raises(ReportNotFoundError):
        await change.execute(ReportId(MISSING_ID), raw_layout(view="x"), 1, viewer(ALICE))


async def test_change_report_layout_of_others_private_report_is_not_found(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 리포트의 배치 저장은 404이고 배치는 그대로다.

    테스트 코드: RS-014
    """
    # given: ALICE의 비공개 리포트
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)
    # when·then: sales·user가 저장하면 둘 다 404다
    for role in (Role.SALES, Role.USER):
        with pytest.raises(ReportNotFoundError):
            await change.execute(report.id, SIDE_RAW, 1, viewer(BOB, role))
    # then: 배치·revision이 그대로다
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (DEFAULT_LAYOUT, 1)


async def test_admin_changes_layout_of_others_private_report(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """admin은 남의 비공개 리포트의 배치도 저장한다.

    테스트 코드: RS-015
    """
    # given: ALICE의 비공개 리포트
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)
    # when: ROOT가 TABLE_ONLY를 저장한다
    result = await change.execute(report.id, TABLE_RAW, 1, viewer(ROOT, Role.ADMIN))
    # then: 배치가 바뀌고 만든 사람은 ALICE, 최종 수정자는 ROOT다
    assert (result.layout, result.owner_user_id, result.updated_by_user_id) == (TABLE, ALICE, ROOT)


async def test_change_report_layout_checks_hidden_before_invalid_layout(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 리포트에 틀린 배치를 보내도 404가 먼저다.

    테스트 코드: RS-046
    """
    # given: ALICE의 비공개 리포트
    report = make_report("비공개", owner=ALICE, visibility="private")
    await seed(uow, report)
    # when·then: BOB이 틀린 배치를 저장하면 404다
    with pytest.raises(ReportNotFoundError):
        await change.execute(report.id, raw_layout(view="x"), 1, viewer(BOB))


async def test_change_report_layout_checks_invalid_layout_before_forbidden(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """수정 권한이 없어도 틀린 배치 값(422)이 403보다 먼저다.

    테스트 코드: RS-046
    """
    # given: 수정 권한 판정을 거짓으로 바꾼 상태의 리포트
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)
    # when·then: BOB이 틀린 배치를 저장하면 배치 값 오류다
    with pytest.raises(ReportDefinitionError):
        await change.execute(report.id, raw_layout(view="x"), 1, viewer(BOB))


async def test_change_report_layout_without_edit_right_is_forbidden(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """수정 권한이 없으면 배치 저장은 403이고 배치는 그대로다.

    테스트 코드: RS-046
    """
    # given: 수정 권한 판정을 거짓으로 바꾼 상태의 리포트
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report("원본", owner=ALICE)
    await seed(uow, report)
    # when·then: BOB이 맞는 배치를 저장하면 수정 권한 오류다
    with pytest.raises(ReportEditForbiddenError) as caught:
        await change.execute(report.id, SIDE_RAW, 1, viewer(BOB))
    assert str(caught.value) == "이 리포트를 수정할 권한이 없습니다."
    # then: 배치·revision이 그대로다
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (DEFAULT_LAYOUT, 1)


async def test_change_report_layout_checks_forbidden_before_conflict(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """수정 권한이 없으면 revision이 낡아도 403이 409보다 먼저다.

    테스트 코드: RS-046
    """
    # given: 수정 권한 판정을 거짓으로 바꾼 상태의 revision 4 리포트
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    report = make_report("원본", owner=ALICE, revision=4)
    await seed(uow, report)
    # when·then: 낡은 revision 1로 저장하면 수정 권한 오류다
    with pytest.raises(ReportEditForbiddenError):
        await change.execute(report.id, SIDE_RAW, 1, viewer(BOB))


async def test_change_report_layout_with_a_stale_revision_conflicts(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """맞는 배치와 권한이 있어도 낡은 revision이면 충돌이고 배치는 그대로다.

    테스트 코드: RS-046
    """
    # given: revision 4인 리포트
    report = make_report("원본", owner=ALICE, revision=4)
    await seed(uow, report)
    # when·then: revision 3으로 저장하면 충돌이다
    with pytest.raises(ReportEditConflictError):
        await change.execute(report.id, SIDE_RAW, 3, viewer(ALICE))
    # then: 배치·revision이 그대로이고 커밋이 없다
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
    """깨진 저장 정의 리포트의 배치 저장은 stored-invalid이고 아무것도 바뀌지 않는다.

    테스트 코드: RS-046
    """
    # given: ALICE의 깨진 정의 리포트
    report = make_broken_report(owner=ALICE)
    await seed(uow, report)
    # when·then: 배치를 저장하면 stored-invalid다
    with pytest.raises(ReportDefinitionError) as caught:
        await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))
    assert _issues(caught) == STORED_INVALID
    # then: 저장 내용이 그대로다
    await _assert_untouched(uow)


async def test_change_report_layout_checks_a_broken_definition_before_the_layout_value(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """깨진 정의 판정(422)이 틀린 배치 값 판정보다 먼저다.

    테스트 코드: RS-046
    """
    # given: ALICE의 깨진 정의 리포트
    report = make_broken_report(owner=ALICE)
    await seed(uow, report)
    # when·then: 틀린 배치를 저장해도 stored-invalid가 나온다
    with pytest.raises(ReportDefinitionError) as caught:
        await change.execute(report.id, raw_layout(view="x"), 1, viewer(ALICE))
    assert _issues(caught) == STORED_INVALID
    # then: 저장 내용이 그대로다
    await _assert_untouched(uow)


async def test_change_report_layout_checks_a_broken_definition_before_forbidden_and_conflict(
    change: ChangeReportLayout, uow: FakeUnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """깨진 정의 판정이 403·409보다 먼저다.

    테스트 코드: RS-046
    """
    # given: revision 4인 ALICE의 깨진 정의 리포트
    report = make_broken_report(owner=ALICE, revision=4)
    await seed(uow, report)
    # when·then: 낡은 revision이어도 stored-invalid다
    with pytest.raises(ReportDefinitionError) as stale:
        await change.execute(report.id, SIDE_RAW, 1, viewer(ALICE))
    # given: 수정 권한 판정을 거짓으로 바꾼다
    monkeypatch.setattr(entities, "can_edit_report", lambda *a, **k: False)
    # when·then: 수정 권한이 없어도 stored-invalid다
    with pytest.raises(ReportDefinitionError) as forbidden:
        await change.execute(report.id, SIDE_RAW, 4, viewer(BOB))
    assert _issues(stale) == _issues(forbidden) == STORED_INVALID
    # then: 저장 내용이 그대로다
    (saved,) = await stored(uow)
    assert (saved.layout, saved.revision) == (DEFAULT_LAYOUT, 4)
    assert uow.commits == 0


async def test_change_report_layout_of_others_private_broken_report_is_not_found(
    change: ChangeReportLayout, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 깨진 리포트의 배치 저장은 404가 먼저다.

    테스트 코드: RS-046
    """
    # given: ALICE의 비공개 깨진 리포트
    report = make_broken_report(owner=ALICE, visibility="private")
    await seed(uow, report)
    # when·then: BOB이 저장하면 404다
    with pytest.raises(ReportNotFoundError):
        await change.execute(report.id, SIDE_RAW, 1, viewer(BOB))
    # then: 저장 내용이 그대로다
    await _assert_untouched(uow)
