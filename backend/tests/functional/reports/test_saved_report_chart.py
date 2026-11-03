"""Feature: 리포트에 차트를 넣어 저장하고, 다시 열고, 고치고, 복제한다.

차트는 그룹핑한 결과의 표시 설정이다. 서버는 차트를 함께 보낸 정의 기준으로 검증하고(어긋나면
저장하지 않는다), 저장한 설정을 정규화해 그대로 돌려준다. 저장된 차트 JSON이 깨져도 리포트는
차트 없이 열린다.
(관련 단위 테스트: tests/unit/domain/test_report_chart_parse.py,
tests/unit/web/test_saved_report_chart_routes.py,
tests/unit/repositories/test_saved_report_chart_contract.py)
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.saved_report_charts import (
    AUTO_BINS,
    CHART_PROBLEM,
    COMBO,
    ONE_GROUP_BODY,
    STACKED_BAR,
    UNGROUPED_BODY,
    chart_report_body,
    chart_report_body_for,
    given_stored_chart_is_unreadable,
    given_stored_chart_json_is,
    legacy_combo_json,
    new_chart,
)
from tests.functional.steps.saved_reports import (
    given_logged_in,
    given_saved_report,
    given_users,
    report_body,
    then_listed_ids_are,
    when_copy_report,
    when_get_report,
    when_list_reports,
    when_run_saved_report,
    when_save_report,
    when_update_report,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_chart_is_saved_and_reopened(api: Api) -> None:
    """Scenario: 누적 막대 차트와 함께 저장하면 상세에 정규화된 차트가, 목록에 종류가 나온다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    chart = {**STACKED_BAR, "title": "  Vendor별 분기 Pipeline  "}
    # When
    saved = await when_save_report(api, chart_report_body("Vendor별 분기", chart))
    # Then
    then_status_is(saved, 201)
    detail = await when_get_report(api, saved.json()["id"])
    then_status_is(detail, 200)
    assert detail.json()["chart"] == STACKED_BAR  # 문자열 앞뒤 공백은 서버가 지운다
    assert detail.json()["chart_problem"] is None
    listed = await when_list_reports(api)
    then_status_is(listed, 200)
    (item,) = [i for i in listed.json() if i["id"] == saved.json()["id"]]
    assert item["chart_kind"] == "stacked_bar"
    assert "chart" not in item


async def test_report_without_a_chart_has_no_chart(api: Api) -> None:
    """Scenario: 차트 없이 저장한 리포트는 chart와 chart_kind가 null이다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    saved = await when_save_report(api, chart_report_body("차트 없음"))
    # Then
    then_status_is(saved, 201)
    then_body_includes(saved, chart=None, chart_problem=None, chart_kind=None)


async def test_chart_invalid_for_the_definition_is_rejected(api: Api) -> None:
    """Scenario: 범주가 값 컬럼인 차트는 422 invalid-report(chart.category)이고 저장되지 않는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    invalid = {**STACKED_BAR, "category": 2}  # index 2는 금액 합계(값 컬럼)
    # When
    response = await when_save_report(api, chart_report_body("잘못된 차트", invalid))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    assert ["chart", "category"] in [e["location"] for e in response.json()["errors"]]
    then_listed_ids_are(await when_list_reports(api), [])


async def test_chart_for_an_ungrouped_definition_is_rejected(api: Api) -> None:
    """Scenario: 그룹핑 없는 정의에 차트를 붙이면 422 invalid-report(["chart"])다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_report(
        api,
        report_body(
            "그룹핑 없음", definition={"columns": [{"field": "deal.code"}]}, chart=STACKED_BAR
        ),
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    assert [e["location"] for e in response.json()["errors"]] == [["chart"]]


async def test_chart_shape_error_is_a_request_validation_error(api: Api) -> None:
    """Scenario: chart에 알 수 없는 키가 있으면 422 request-validation이다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_report(
        api, chart_report_body("모양 오류", {**STACKED_BAR, "colour": "red"})
    )
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_overwrite_changes_and_removes_the_chart(api: Api) -> None:
    """Scenario: 차트만 바꿔 덮어써도 revision이 오르고, chart 없이 덮어쓰면 차트가 지워진다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(
        api, "원본", definition=chart_report_body()["definition"], chart=STACKED_BAR
    )
    # When
    changed = await when_update_report(
        api, saved["id"], {**chart_report_body("원본", COMBO), "revision": 1}
    )
    cleared = await when_update_report(
        api, saved["id"], {**chart_report_body("원본"), "revision": 2}
    )
    # Then
    then_status_is(changed, 200)
    then_body_includes(changed, revision=2, chart=COMBO, chart_kind="combo")
    assert changed.json()["generated_sql"] == saved["generated_sql"]  # 차트와 무관
    then_status_is(cleared, 200)
    then_body_includes(cleared, revision=3, chart=None, chart_kind=None)
    listed = await when_list_reports(api)
    assert [i["chart_kind"] for i in listed.json() if i["id"] == saved["id"]] == [None]


async def test_overwrite_with_a_chart_that_no_longer_fits_is_rejected(api: Api) -> None:
    """Scenario: 정의의 그룹핑을 끄고 이전 차트를 그대로 보내면 422이고 저장된 내용은 그대로다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(
        api, "원본", definition=chart_report_body()["definition"], chart=STACKED_BAR
    )
    # When
    response = await when_update_report(
        api,
        saved["id"],
        {
            **report_body(
                "원본", definition={"columns": [{"field": "deal.code"}]}, chart=STACKED_BAR
            ),
            "revision": 1,
        },
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    reread = await when_get_report(api, saved["id"])
    then_body_includes(reread, revision=1, chart=STACKED_BAR)
    assert reread.json()["definition"] == saved["definition"]


async def test_copy_carries_the_chart(api: Api) -> None:
    """Scenario: 복제하면 원본의 차트가 정의와 함께 복제된다."""
    # Given
    await given_users(api, alice="sales", bob="user")
    await given_logged_in(api, "alice")
    source = await given_saved_report(
        api, "원본", definition=chart_report_body()["definition"], chart=STACKED_BAR
    )
    await given_logged_in(api, "bob")
    # When
    response = await when_copy_report(
        api, source["id"], {"name": "원본 복사본", "visibility": "private"}
    )
    # Then
    then_status_is(response, 201)
    then_body_includes(response, chart=STACKED_BAR, chart_kind="stacked_bar", chart_problem=None)


async def test_unreadable_stored_chart_opens_without_chart(api: Api) -> None:
    """Scenario: 저장된 chart JSON이 깨져도 목록·상세·실행은 되고, 새 차트로 덮어쓰면 복구된다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(
        api, "깨질 차트", definition=chart_report_body()["definition"], chart=STACKED_BAR
    )
    await given_stored_chart_is_unreadable(api, saved["id"], "[1]")
    # When
    listed = await when_list_reports(api)
    detail = await when_get_report(api, saved["id"])
    run = await when_run_saved_report(api, saved["id"])
    # Then
    then_status_is(listed, 200)
    assert [i["chart_kind"] for i in listed.json() if i["id"] == saved["id"]] == [None]
    then_status_is(detail, 200)
    then_body_includes(detail, chart=None, chart_problem=CHART_PROBLEM, revision=1)
    then_status_is(run, 200)
    # When (복구)
    repaired = await when_update_report(
        api, saved["id"], {**chart_report_body("깨질 차트", COMBO), "revision": 1}
    )
    # Then
    then_status_is(repaired, 200)
    then_body_includes(repaired, chart=COMBO, chart_problem=None, revision=2)


NEW_KIND_CASES = {
    "stacked_horizontal_bar": new_chart("stacked_horizontal_bar", series=1, values=[2]),
    "treemap": new_chart("treemap", series=1, values=[2]),
    "bubble": new_chart("bubble", values=[1, 2, 3]),
    "waterfall": new_chart("waterfall", values=[1], show_total=True),
    "combo": new_chart(
        "combo",
        values=[1, 2],
        secondary_axis=True,
        combo_series=[
            {"type": "stacked_area", "secondary": False},
            {"type": "line_markers", "secondary": True},
        ],
    ),
}


@pytest.mark.parametrize("kind", list(NEW_KIND_CASES))
async def test_saving_and_reading_each_new_chart_kind(api: Api, kind: str) -> None:
    """Scenario: 새 종류 차트는 저장하면 같은 설정으로 상세에, 같은 종류로 목록에 나온다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    chart = NEW_KIND_CASES[kind]
    definition = chart_report_body()["definition"] if chart["series"] == 1 else ONE_GROUP_BODY
    # When
    saved = await when_save_report(api, chart_report_body_for(f"새 종류 {kind}", definition, chart))
    # Then
    then_status_is(saved, 201)
    detail = await when_get_report(api, saved.json()["id"])
    then_status_is(detail, 200)
    assert detail.json()["chart"] == chart
    listed = await when_list_reports(api)
    (item,) = [i for i in listed.json() if i["id"] == saved.json()["id"]]
    assert item["chart_kind"] == kind


async def test_saving_an_ungrouped_histogram_report(api: Api) -> None:
    """Scenario: 그룹핑 없는 금액 컬럼으로 히스토그램을 저장하면 category는 null, 구간은 auto다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    chart = new_chart("histogram", category=None, values=[1])
    # When
    saved = await when_save_report(api, chart_report_body_for("금액 분포", UNGROUPED_BODY, chart))
    # Then
    then_status_is(saved, 201)
    assert saved.json()["chart"]["category"] is None
    assert saved.json()["chart"]["histogram"] == AUTO_BINS
    assert saved.json()["chart_kind"] == "histogram"


async def test_invalid_histogram_bins_are_rejected(api: Api) -> None:
    """Scenario: 구간 수가 범위를 벗어나면 422 invalid-report(chart.histogram.bin_count)다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    bins = {**AUTO_BINS, "bin_mode": "count", "bin_count": 101}
    chart = new_chart("histogram", category=None, values=[1], histogram=bins)
    # When
    response = await when_save_report(
        api, chart_report_body_for("잘못된 구간", UNGROUPED_BODY, chart)
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    assert ["chart", "histogram", "bin_count"] in [e["location"] for e in response.json()["errors"]]
    then_listed_ids_are(await when_list_reports(api), [])


@pytest.mark.parametrize("secondary", [False, True])
async def test_reading_a_legacy_combo_chart(api: Api, secondary: bool) -> None:
    """Scenario: 계열별 설정이 없는 옛 콤보 행은 첫 값 열 막대, 나머지 꺾은선으로 읽힌다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "옛 콤보", definition=ONE_GROUP_BODY, chart=None)
    await given_stored_chart_json_is(api, saved["id"], legacy_combo_json(secondary_axis=secondary))
    # When
    detail = await when_get_report(api, saved["id"])
    # Then
    then_status_is(detail, 200)
    assert detail.json()["chart_problem"] is None
    assert detail.json()["chart"]["combo_series"] == [
        {"type": "column", "secondary": False},
        {"type": "line", "secondary": secondary},
        {"type": "line", "secondary": secondary},
    ]
