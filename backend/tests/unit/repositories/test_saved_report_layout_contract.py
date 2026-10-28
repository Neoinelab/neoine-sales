"""ReportRepository 결과 배치 계약 (AC18, 25, 26): Fake와 SQL 구현 공통 테스트.

배치는 `reports.layout`(JSONB, NULL 가능)에 `{view, order, arrange}`로 저장된다. NULL이거나 읽을
수 없는 값은 기본 배치로 읽힌다. `update_layout`은 배치와 수정 정보(수정자·revision·수정 시각)만
쓰고 정의·차트 JSON은 다시 쓰지 않는다.
"""

from typing import TYPE_CHECKING

import pytest
from app.domain.saved_report.layout import DEFAULT_LAYOUT

from app.domain.auth.principal import Role
from app.domain.saved_report.errors import ReportNotFoundError
from app.domain.saved_report.values import ReportId
from tests.factories import later
from tests.factories_report import make_content, make_report
from tests.support.chart_defs import chart_definition, raw_chart
from tests.support.ids import MISSING_ID
from tests.support.layout_defs import make_layout
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.saved_report_case import SavedReportCase

ALICE = uid("layout-contract-alice")
BOB = uid("layout-contract-bob")
SIDE = make_layout("chart", ("chart", "table"), "side_by_side")
TABLE = make_layout("table", ("table", "chart"), "stacked")
BAR = raw_chart("bar", 0, [1])


async def test_add_and_get_round_trips_layout(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("배치 왕복", owner=ALICE, layout=SIDE))

    stored = await saved_report_case.reports.get(report.id)

    assert stored.layout == SIDE
    assert stored == report


async def test_add_without_layout_round_trips_the_default(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("기본 배치", owner=ALICE))

    assert (await saved_report_case.reports.get(report.id)).layout == DEFAULT_LAYOUT


async def test_get_null_layout_column_returns_default(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("널 배치", owner=ALICE, layout=SIDE))
    await saved_report_case.set_layout_json(report, None)

    stored = await saved_report_case.reports.get(report.id)

    assert stored.layout == DEFAULT_LAYOUT
    assert (stored.name, stored.revision) == ("널 배치", 1)


@pytest.mark.parametrize(
    "raw_json",
    [
        '{"view": "x", "order": ["table", "chart"], "arrange": "stacked"}',
        '{"view": "both"}',
        '{"view": "both", "order": ["table", "table"], "arrange": "stacked"}',
        "{}",
    ],
)
async def test_get_unreadable_layout_value_returns_default(
    saved_report_case: SavedReportCase, raw_json: str
) -> None:
    report = await saved_report_case.add(make_report("깨진 배치", owner=ALICE, layout=SIDE))
    await saved_report_case.set_layout_json(report, raw_json)

    assert (await saved_report_case.reports.get(report.id)).layout == DEFAULT_LAYOUT


async def test_update_replaces_the_layout(saved_report_case: SavedReportCase) -> None:
    report = await saved_report_case.add(make_report("교체", owner=ALICE, layout=SIDE))
    stored = await saved_report_case.reports.get(report.id)
    stored.overwrite(
        make_content("교체", layout=TABLE),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    again = await saved_report_case.reports.get(report.id)
    assert (again.layout, again.revision) == (TABLE, 2)


async def test_update_without_a_new_layout_keeps_the_stored_one(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("유지", owner=ALICE, layout=SIDE))
    stored = await saved_report_case.reports.get(report.id)
    stored.overwrite(
        make_content("유지 이름 변경"),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    assert (await saved_report_case.reports.get(report.id)).layout == SIDE


async def test_update_after_a_null_layout_column_writes_the_default_object(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("널 뒤 저장", owner=ALICE, layout=SIDE))
    await saved_report_case.set_layout_json(report, None)
    stored = await saved_report_case.reports.get(report.id)
    stored.overwrite(
        make_content("널 뒤 저장 변경"),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    assert (await saved_report_case.reports.get(report.id)).layout == DEFAULT_LAYOUT


async def test_list_carries_the_layout_of_each_report(saved_report_case: SavedReportCase) -> None:
    from app.domain.saved_report.values import ReportListScope  # noqa: PLC0415

    first = await saved_report_case.add(
        make_report("목록 하나", owner=ALICE, layout=SIDE, updated_at=later(20))
    )
    second = await saved_report_case.add(make_report("목록 둘", owner=ALICE, updated_at=later(10)))

    listed = await saved_report_case.mine(
        ReportListScope(viewer_id=ALICE, see_all=True), {first.id, second.id}
    )

    assert [(r.name, r.layout) for r in listed] == [
        ("목록 하나", SIDE),
        ("목록 둘", DEFAULT_LAYOUT),
    ]


async def test_update_layout_writes_the_layout_and_audit_fields(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(
        make_report("배치만", owner=ALICE, definition=chart_definition(1, 3), chart=BAR)
    )
    await saved_report_case.prepare(BOB)
    stored = await saved_report_case.reports.get(report.id)
    stored.change_layout(SIDE, editor=BOB, role=Role.SALES, expected_revision=1, now=later(7))

    await saved_report_case.reports.update_layout(stored)

    again = await saved_report_case.reports.get(report.id)
    assert again.layout == SIDE
    assert (again.revision, again.updated_by_user_id, again.updated_at) == (2, BOB, later(7))
    assert again.owner_user_id == ALICE
    assert (again.name, again.definition, again.chart, again.generated_sql) == (
        report.name,
        report.definition,
        BAR,
        report.generated_sql,
    )


async def test_update_layout_writes_only_layout_and_audit(
    saved_report_case: SavedReportCase,
) -> None:
    report = await saved_report_case.add(make_report("깨진 채 배치", owner=ALICE, chart=BAR))
    await saved_report_case.corrupt_definition(report, '{"columns": "x"}')
    await saved_report_case.corrupt_chart(report, "[1]")
    broken = await saved_report_case.reports.get(report.id)
    assert broken.definition is None
    assert broken.chart_unreadable is True
    broken.change_layout(SIDE, editor=ALICE, role=Role.SALES, expected_revision=1, now=later(3))

    await saved_report_case.reports.update_layout(broken)

    again = await saved_report_case.reports.get(report.id)
    assert again.layout == SIDE
    assert (again.revision, again.updated_at) == (2, later(3))
    assert again.definition is None  # 깨진 정의 JSON을 다시 쓰지 않았다
    assert (again.chart, again.chart_unreadable) == (None, True)  # 깨진 차트 JSON도 그대로


async def test_update_layout_does_not_touch_other_reports(
    saved_report_case: SavedReportCase,
) -> None:
    mine = await saved_report_case.add(make_report("내 것", owner=ALICE, layout=SIDE))
    other = await saved_report_case.add(make_report("남의 것", owner=ALICE))
    stored = await saved_report_case.reports.get(mine.id)
    stored.change_layout(TABLE, editor=ALICE, role=Role.SALES, expected_revision=1, now=later(1))

    await saved_report_case.reports.update_layout(stored)

    untouched = await saved_report_case.reports.get(other.id)
    assert (untouched.layout, untouched.revision) == (DEFAULT_LAYOUT, 1)


async def test_update_layout_missing_report_raises_not_found(
    saved_report_case: SavedReportCase,
) -> None:
    ghost = make_report("없음", owner=ALICE, report_id=ReportId(MISSING_ID), layout=SIDE)
    await saved_report_case.prepare(ALICE)

    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.update_layout(ghost)
