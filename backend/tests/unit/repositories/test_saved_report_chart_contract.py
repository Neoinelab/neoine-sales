"""ReportRepository 차트 계약: Fake와 SQL 구현 공통 테스트(RC-R18, RC-R21, RC-R22).

차트는 `reports.chart`(JSONB, NULL 가능)에 정규화된 16개 키로 저장된다. 읽을 수 없는 차트는
리포트를 막지 않고 "차트 없음 + 읽을 수 없음"으로 읽힌다(목록·상세·수정·삭제는 계속 된다).
"""

import json
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from app.domain.report.chart_kinds import ChartKind
from app.domain.saved_report.values import ReportListScope
from tests.factories import later
from tests.factories_report import make_content, make_report
from tests.support.chart_defs import bins, chart_body, chart_definition, combo_item, raw_chart
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
    value_axis_title="금액 (원)",
    value_min=-0.5,
    value_max=1000,
    secondary_axis=False,
)
BROKEN_CHART_JSON = [
    "[1]",
    '{"kind": "x"}',
    '{"kind": "bar", "category": "0", "values": [1]}',
    '{"kind": "combo", "category": 0, "values": [1, 2],'
    ' "combo_series": [{"type": "pie", "secondary": false}, {"type": "line", "secondary": false}]}',
    '{"kind": "histogram", "category": null, "values": [1], "histogram": {"bin_mode": "foo",'
    ' "bin_count": null, "bin_width": null, "overflow": null, "underflow": null}}',
]


def _scope() -> ReportListScope:
    return ReportListScope(viewer_id=ALICE, see_all=True)


async def test_chart_round_trips_with_all_sixteen_keys(saved_report_case: SavedReportCase) -> None:
    """차트는 16키 모두 저장소를 거쳐 같은 값으로 돌아온다."""
    # given: 모든 옵션을 채운 차트를 가진 저장 리포트
    report = make_report("차트 왕복", owner=ALICE, definition=DEFINITION, chart=FULL)
    await saved_report_case.add(report)

    # when: 리포트를 다시 읽는다
    stored = await saved_report_case.reports.get(report.id)

    # then: 차트·종류·읽을 수 없음 표시가 저장한 그대로다
    assert stored.chart == FULL
    assert stored.chart_unreadable is False
    assert stored.chart_kind() == ChartKind.STACKED_BAR
    assert stored == report


async def test_none_chart_stays_none(saved_report_case: SavedReportCase) -> None:
    """차트가 없으면 읽어도 차트·종류가 없고 읽을 수 없음 표시도 없다."""
    # given: 차트 없는 저장 리포트
    report = await saved_report_case.add(make_report("차트 없음", owner=ALICE))

    # when: 리포트를 다시 읽는다
    stored = await saved_report_case.reports.get(report.id)

    # then: 차트·종류가 None이고 읽을 수 없음 표시가 꺼져 있다
    assert (stored.chart, stored.chart_unreadable, stored.chart_kind()) == (None, False, None)


async def test_chart_defaults_round_trip(saved_report_case: SavedReportCase) -> None:
    """기본값 차트(범례 위, 범위 없음, 빈 제목)도 그대로 왕복한다."""
    # given: 기본값만 가진 원형 차트를 가진 저장 리포트
    chart = raw_chart("pie", 0, [2])
    report = await saved_report_case.add(make_report("기본값", owner=ALICE, chart=chart))

    # when: 리포트를 다시 읽는다
    stored = await saved_report_case.reports.get(report.id)

    # then: 차트가 같고 범례·범위·제목이 기본값이다
    assert stored.chart == chart
    assert stored.chart is not None
    assert (stored.chart.legend, stored.chart.value_min, stored.chart.title) == ("top", None, "")


async def test_list_carries_the_chart_of_each_report(saved_report_case: SavedReportCase) -> None:
    """목록 조회는 리포트마다 차트 종류를 싣는다.

    테스트 코드: RC-037
    """
    # given: 차트가 있는 리포트와 없는 리포트
    with_chart = await saved_report_case.add(
        make_report("차트 있음", owner=ALICE, chart=FULL, updated_at=later(20))
    )
    without = await saved_report_case.add(
        make_report("차트 없음", owner=ALICE, updated_at=later(10))
    )

    # when: 내 리포트 목록을 조회한다
    listed = await saved_report_case.mine(_scope(), {with_chart.id, without.id})

    # then: 차트 있음은 누적 막대, 없음은 None이다
    assert [(r.name, r.chart_kind()) for r in listed] == [
        ("차트 있음", ChartKind.STACKED_BAR),
        ("차트 없음", None),
    ]


async def test_update_replaces_the_chart(saved_report_case: SavedReportCase) -> None:
    """차트를 바꿔 저장하면 새 차트와 revision이 저장소에 남는다.

    테스트 코드: RC-035
    """
    # given: 차트가 있는 저장 리포트
    report = await saved_report_case.add(
        make_report("교체", owner=ALICE, chart=raw_chart("bar", 0, [2]))
    )
    stored = await saved_report_case.reports.get(report.id)
    # when: 차트를 바꿔 덮어쓰고 저장소에 반영한다
    stored.overwrite(
        make_content("교체", chart=FULL),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    # then: 새 차트이고 revision 2다
    again = await saved_report_case.reports.get(report.id)
    assert again.chart == FULL
    assert again.revision == 2


async def test_update_clears_the_chart(saved_report_case: SavedReportCase) -> None:
    """차트를 지워 저장하면 차트와 종류가 모두 없어진다.

    테스트 코드: RC-035
    """
    # given: 차트가 있는 저장 리포트
    report = await saved_report_case.add(make_report("삭제", owner=ALICE, chart=FULL))
    stored = await saved_report_case.reports.get(report.id)
    # when: 차트를 바꿔 덮어쓰고 저장소에 반영한다
    stored.overwrite(
        make_content("삭제", chart=None),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    # then: 차트·종류가 None이다
    again = await saved_report_case.reports.get(report.id)
    assert (again.chart, again.chart_kind()) == (None, None)


async def test_update_without_touching_the_chart_keeps_it(
    saved_report_case: SavedReportCase,
) -> None:
    """차트를 그대로 둔 채 저장해도 차트가 유지된다."""
    # given: 차트가 있는 저장 리포트
    report = await saved_report_case.add(make_report("유지", owner=ALICE, chart=FULL))
    stored = await saved_report_case.reports.get(report.id)
    # when: 차트를 바꿔 덮어쓰고 저장소에 반영한다
    stored.overwrite(
        make_content("유지", chart=stored.chart),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(stored)

    # then: 차트가 그대로다
    assert (await saved_report_case.reports.get(report.id)).chart == FULL


@pytest.mark.parametrize("raw_json", BROKEN_CHART_JSON)
async def test_get_reads_an_unreadable_chart_as_no_chart(
    saved_report_case: SavedReportCase, raw_json: str
) -> None:
    """읽을 수 없는 차트 JSON은 차트 없음 + 읽을 수 없음으로 읽히고 정의는 정상이다.

    테스트 코드: RC-040
    """
    # given: 차트 JSON이 깨진 저장 리포트
    report = await saved_report_case.add(
        make_report("깨진 차트", owner=ALICE, description="설명", chart=FULL)
    )
    await saved_report_case.corrupt_chart(report, raw_json)

    # when: 리포트를 읽는다
    stored = await saved_report_case.reports.get(report.id)

    # then: 차트는 None, 읽을 수 없음 표시와 종류 None이며 이름·설명·revision·정의는 정상이다
    assert stored.chart is None
    assert stored.chart_unreadable is True
    assert stored.chart_kind() is None
    assert (stored.name, stored.description, stored.revision) == ("깨진 차트", "설명", 1)
    assert stored.definition == report.definition  # 정의는 정상으로 읽힌다


async def test_list_does_not_fail_on_an_unreadable_chart(
    saved_report_case: SavedReportCase,
) -> None:
    """목록은 읽을 수 없는 차트가 있어도 실패하지 않는다.

    테스트 코드: RC-040
    """
    # given: 정상 리포트와 차트 JSON이 깨진 리포트
    healthy = await saved_report_case.add(
        make_report("정상", owner=ALICE, chart=FULL, updated_at=later(10))
    )
    broken = await saved_report_case.add(
        make_report("깨짐", owner=ALICE, chart=FULL, updated_at=later(20))
    )
    await saved_report_case.corrupt_chart(broken, "[1]")

    # when: 내 리포트 목록을 조회한다
    listed = await saved_report_case.mine(_scope(), {healthy.id, broken.id})

    # then: 깨진 리포트는 종류 None·읽을 수 없음, 정상 리포트는 누적 막대다
    assert [(r.name, r.chart_kind(), r.chart_unreadable) for r in listed] == [
        ("깨짐", None, True),
        ("정상", ChartKind.STACKED_BAR, False),
    ]


async def test_update_with_a_new_chart_repairs_an_unreadable_one(
    saved_report_case: SavedReportCase,
) -> None:
    """새 차트로 덮어쓰면 읽을 수 없던 차트가 복구된다.

    테스트 코드: RC-041
    """
    # given: 차트 JSON이 깨진 저장 리포트
    report = await saved_report_case.add(make_report("복구 대상", owner=ALICE, chart=FULL))
    await saved_report_case.corrupt_chart(report, '{"kind": "x"}')
    broken = await saved_report_case.reports.get(report.id)
    # when: 새 차트로 덮어쓰고 저장소에 반영한다
    broken.overwrite(
        make_content("복구 대상", chart=FULL),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(broken)

    # then: 새 차트가 읽히고 읽을 수 없음 표시가 꺼지며 revision 2다
    stored = await saved_report_case.reports.get(report.id)
    assert (stored.chart, stored.chart_unreadable, stored.revision) == (FULL, False, 2)


async def test_update_without_a_chart_repairs_an_unreadable_one(
    saved_report_case: SavedReportCase,
) -> None:
    """차트 없이 덮어써도 읽을 수 없음 상태가 복구된다.

    테스트 코드: RC-041
    """
    # given: 차트 JSON이 깨진 저장 리포트
    report = await saved_report_case.add(make_report("차트 없이 복구", owner=ALICE, chart=FULL))
    await saved_report_case.corrupt_chart(report, "[1]")
    broken = await saved_report_case.reports.get(report.id)
    # when: 차트 없이 덮어쓰고 저장소에 반영한다
    broken.overwrite(
        make_content("차트 없이 복구", chart=None),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )

    await saved_report_case.reports.update(broken)

    # then: 차트는 None이고 읽을 수 없음 표시가 꺼진다
    stored = await saved_report_case.reports.get(report.id)
    assert (stored.chart, stored.chart_unreadable) == (None, False)


async def test_delete_removes_a_report_with_an_unreadable_chart(
    saved_report_case: SavedReportCase,
) -> None:
    """차트를 읽을 수 없는 리포트도 삭제할 수 있다.

    테스트 코드: RC-041
    """
    from app.domain.saved_report.errors import ReportNotFoundError  # noqa: PLC0415

    # given: 차트 JSON이 깨진 저장 리포트
    report = await saved_report_case.add(make_report("깨진 차트 삭제", owner=ALICE, chart=FULL))
    await saved_report_case.corrupt_chart(report, "[1]")

    # when: 리포트를 삭제한다
    await saved_report_case.reports.delete(report.id)

    # then: 다시 읽으면 찾을 수 없다는 오류가 난다
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(report.id)


def _new_key_chart(name: str) -> Any:  # noqa: ANN401 - RawChart
    return {
        "histogram": raw_chart(
            "histogram", None, [2], histogram=bins(bin_mode="count", bin_count=7)
        ),
        "waterfall": raw_chart("waterfall", 0, [2], show_total=True),
        "combo": raw_chart(
            "combo",
            0,
            [2, 3],
            secondary_axis=True,
            combo_series=[combo_item("stacked_area"), combo_item("line_markers", secondary=True)],
        ),
        "treemap": raw_chart("treemap", 0, [2], series=1),
    }[name]


@pytest.mark.parametrize("name", ["histogram", "waterfall", "combo", "treemap"])
async def test_new_chart_keys_round_trip_through_storage(
    saved_report_case: SavedReportCase, name: str
) -> None:
    """새 키(구간·합계·콤보 계열)가 있는 차트도 저장소를 거쳐 그대로 돌아온다."""
    # given: 새 옵션을 가진 차트의 저장 리포트
    chart = _new_key_chart(name)
    report = await saved_report_case.add(
        make_report("새 키 왕복", owner=ALICE, definition=DEFINITION, chart=chart)
    )

    # when: 리포트를 다시 읽는다
    stored = await saved_report_case.reports.get(report.id)

    # then: 차트·종류가 그대로이고 읽을 수 없음 표시가 꺼져 있다
    assert stored.chart == chart
    assert stored.chart_unreadable is False
    assert stored.chart_kind() == ChartKind(name)


async def test_legacy_combo_row_is_read_with_the_legacy_series_rule(
    saved_report_case: SavedReportCase,
) -> None:
    """옛 형식(새 키 3개 없음)으로 저장된 콤보 행은 옛 규칙으로 계열 설정이 채워져 읽힌다.

    테스트 코드: RC-044
    """
    # given: 저장 열이 옛 13키 콤보 JSON인 리포트
    report = await saved_report_case.add(make_report("옛 콤보", owner=ALICE, chart=FULL))
    legacy = {
        k: v
        for k, v in chart_body("combo", 0, values=[2, 3, 4], secondary_axis=True).items()
        if k not in {"histogram", "show_total", "combo_series"}
    }
    await saved_report_case.set_chart_json(report, json.dumps(legacy))

    # when: 리포트를 읽는다
    stored = await saved_report_case.reports.get(report.id)

    # then: 첫 값은 묶은 세로 막대, 나머지는 보조 축 꺾은선이다
    assert stored.chart_unreadable is False
    assert stored.chart_kind() == ChartKind.COMBO
    assert stored.chart is not None
    assert stored.chart.combo_series == [
        combo_item("column"),
        combo_item("line", secondary=True),
        combo_item("line", secondary=True),
    ]


async def test_legacy_thirteen_key_bar_row_reads_with_default_new_keys(
    saved_report_case: SavedReportCase,
) -> None:
    """옛 13키 막대 행은 새 키가 기본값으로 읽힌다.

    테스트 코드: RC-043
    """
    # given: 저장 열이 옛 13키 막대 JSON인 리포트
    report = await saved_report_case.add(make_report("옛 막대", owner=ALICE, chart=FULL))
    legacy = {
        k: v
        for k, v in chart_body("bar", 0, values=[2]).items()
        if k not in {"histogram", "show_total", "combo_series"}
    }
    await saved_report_case.set_chart_json(report, json.dumps(legacy))

    # when: 리포트를 읽는다
    stored = await saved_report_case.reports.get(report.id)

    # then: 차트가 기본 막대와 같고 구간·합계·계열 설정이 기본값이다
    assert stored.chart == raw_chart("bar", 0, [2])
    assert (stored.chart.histogram, stored.chart.show_total, stored.chart.combo_series) == (
        None,
        False,
        None,
    )
