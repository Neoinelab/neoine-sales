"""Feature: 리포트의 결과 배치(보기 방식, 표·차트 순서, 한 줄/두 줄)를 저장하고 다시 연다.

배치는 조회 정의·차트와 별개로 저장된다. 만들기·덮어쓰기·복제에 포함되고, 배치만 바꾸는 전용
API는 정의·차트·이름을 건드리지 않은 채 revision을 올린다(낙관적 잠금). 저장된 배치가 없거나
읽을 수 없으면 기본 배치(표+차트, 표 -> 차트, 두 줄)로 열린다.
(관련 단위 테스트: tests/unit/domain/test_saved_report_layout.py,
tests/unit/application/test_saved_report_layout.py,
tests/unit/web/test_saved_report_layout_routes.py,
tests/unit/repositories/test_saved_report_layout_contract.py)
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.saved_report_charts import (
    CHART_PROBLEM,
    STACKED_BAR,
    chart_report_body,
    given_stored_chart_is_unreadable,
)
from tests.functional.steps.saved_report_layouts import (
    BOTH_SIDE,
    CHART_FIRST_SIDE,
    DEFAULT_LAYOUT,
    TABLE_ONLY,
    given_stored_layout_is_null,
    then_detail_layout_is,
    when_layouts_saved_in_sequence,
    when_save_layout,
)
from tests.functional.steps.saved_reports import (
    given_logged_in,
    given_report_overwritten,
    given_saved_report,
    given_stored_definition_is_unreadable,
    given_users,
    report_body,
    then_hidden_looks_like_missing,
    when_copy_report,
    when_get_report,
    when_save_report,
    when_update_report,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
DEFINITION = chart_report_body()["definition"]


async def test_saved_layout_is_returned_on_open(api: Api) -> None:
    """Scenario: 배치를 정해 저장하면 같은 보기 방식·순서·한 줄/두 줄로 다시 열린다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    saved = await when_save_report(api, report_body("배치 저장", layout=CHART_FIRST_SIDE))
    # Then
    then_status_is(saved, 201)
    assert saved.json()["layout"] == CHART_FIRST_SIDE
    await then_detail_layout_is(api, saved.json()["id"], CHART_FIRST_SIDE, revision=1)


async def test_report_without_layout_opens_with_default_layout(api: Api) -> None:
    """Scenario: layout 없이 저장한 리포트는 기본 배치로 열리고 다른 응답 필드는 그대로다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    saved = await when_save_report(api, report_body("배치 없음"))
    # Then
    then_status_is(saved, 201)
    then_body_includes(saved, layout=DEFAULT_LAYOUT, revision=1, chart=None, name="배치 없음")
    await then_detail_layout_is(api, saved.json()["id"], DEFAULT_LAYOUT)


async def test_report_with_a_null_layout_row_opens_with_default_layout(api: Api) -> None:
    """Scenario: 배치 열이 NULL인 기존 리포트는 오류 없이 기본 배치로 열린다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "기존 행", layout=CHART_FIRST_SIDE)
    await given_stored_layout_is_null(api, saved["id"])
    # When
    response = await when_get_report(api, saved["id"])
    # Then
    then_status_is(response, 200)
    then_body_includes(response, layout=DEFAULT_LAYOUT, revision=1)


async def test_update_without_layout_keeps_the_stored_layout(api: Api) -> None:
    """Scenario: layout 없이 덮어써도 저장된 배치가 유지된다(차트와 달리 생략이 삭제가 아니다)."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본", layout=CHART_FIRST_SIDE)
    # When
    response = await when_update_report(
        api, saved["id"], {**report_body("새 이름"), "revision": saved["revision"]}
    )
    # Then
    then_status_is(response, 200)
    then_body_includes(response, name="새 이름", revision=2, layout=CHART_FIRST_SIDE)
    await then_detail_layout_is(api, saved["id"], CHART_FIRST_SIDE, revision=2)


async def test_update_with_layout_replaces_the_stored_layout(api: Api) -> None:
    """Scenario: layout을 함께 보내 덮어쓰면 배치가 바뀐다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본", layout=CHART_FIRST_SIDE)
    # When
    response = await when_update_report(
        api, saved["id"], {**report_body("원본", layout=TABLE_ONLY), "revision": 1}
    )
    # Then
    then_status_is(response, 200)
    then_body_includes(response, layout=TABLE_ONLY, revision=2)
    await then_detail_layout_is(api, saved["id"], TABLE_ONLY, revision=2)


async def test_copy_keeps_source_layout(api: Api) -> None:
    """Scenario: 복제하면 원본에 저장된 배치가 그대로 복사된다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    source = await given_saved_report(api, "원본", layout=BOTH_SIDE)
    await given_logged_in(api, "bob")
    # When
    copied = await when_copy_report(api, source["id"], {"name": "복사본", "visibility": "public"})
    # Then
    then_status_is(copied, 201)
    then_body_includes(copied, layout=BOTH_SIDE, revision=1)
    await then_detail_layout_is(api, copied.json()["id"], BOTH_SIDE)


async def test_owner_saves_layout_only(api: Api) -> None:
    """Scenario: 배치만 저장하면 revision이 오르고 정의·차트·이름은 그대로, 수정자는 본인이다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "Vendor별 분기", definition=DEFINITION, chart=STACKED_BAR)
    # When
    response = await when_save_layout(api, saved["id"], CHART_FIRST_SIDE, saved["revision"])
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["layout"] == CHART_FIRST_SIDE
    assert body["revision"] == saved["revision"] + 1
    for key in ("name", "definition", "generated_sql", "chart", "visibility", "owner"):
        assert body[key] == saved[key], key
    assert body["updated_by"] == saved["owner"]
    await then_detail_layout_is(api, saved["id"], CHART_FIRST_SIDE, revision=2)


async def test_layout_save_leaves_an_unreadable_stored_chart_untouched(api: Api) -> None:
    """Scenario: 깨진 저장 차트가 있어도 배치만 저장되고 차트 안내는 그대로 남는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "깨진 차트", definition=DEFINITION, chart=STACKED_BAR)
    await given_stored_chart_is_unreadable(api, saved["id"], "[1]")
    # When
    response = await when_save_layout(api, saved["id"], TABLE_ONLY, 1)
    # Then
    then_status_is(response, 200)
    then_body_includes(
        response, layout=TABLE_ONLY, revision=2, chart=None, chart_problem=CHART_PROBLEM
    )
    reopened = await when_get_report(api, saved["id"])
    then_body_includes(reopened, chart=None, chart_problem=CHART_PROBLEM, layout=TABLE_ONLY)


async def test_consecutive_layout_saves_use_returned_revision(api: Api) -> None:
    """Scenario: 응답 revision으로 배치를 세 번 연달아 저장하면 모두 성공하고 낡은 값은 409다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "연속 저장")
    # When
    responses = await when_layouts_saved_in_sequence(
        api, saved, [CHART_FIRST_SIDE, BOTH_SIDE, TABLE_ONLY]
    )
    # Then
    assert [r.status_code for r in responses] == [200, 200, 200]
    assert [r.json()["revision"] for r in responses] == [2, 3, 4]
    await then_detail_layout_is(api, saved["id"], TABLE_ONLY, revision=4)
    stale = await when_save_layout(api, saved["id"], CHART_FIRST_SIDE, 1)
    then_problem_is(stale, status=409, type_suffix="invalid-state")
    await then_detail_layout_is(api, saved["id"], TABLE_ONLY, revision=4)


async def test_layout_save_hides_private_report_of_others(api: Api) -> None:
    """Scenario: 남의 비공개 리포트의 배치 저장은 없는 id와 같은 404이고 배치는 그대로다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    private = await given_saved_report(api, "비공개", visibility="private", layout=BOTH_SIDE)
    await given_logged_in(api, "bob")
    # When
    response = await when_save_layout(api, private["id"], TABLE_ONLY, 1)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    await then_hidden_looks_like_missing(api, response, "LAYOUT")
    await given_logged_in(api, "alice")
    await then_detail_layout_is(api, private["id"], BOTH_SIDE, revision=1)


async def test_layout_save_with_stale_revision_conflicts(api: Api) -> None:
    """Scenario: 다른 사람이 먼저 덮어쓴 뒤 이전 revision으로 배치를 저장하면 409이고 그대로다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in(api, "bob")
    overwritten = await given_report_overwritten(api, saved, "공개", visibility="public")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_layout(api, saved["id"], TABLE_ONLY, saved["revision"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    await then_detail_layout_is(api, saved["id"], DEFAULT_LAYOUT, revision=overwritten["revision"])


async def test_others_public_report_layout_can_be_saved_and_records_the_editor(api: Api) -> None:
    """Scenario: 남의 공개 리포트도 배치를 저장할 수 있고 만든 사람은 그대로, 수정자는 나다."""
    # Given
    await given_users(api, alice="sales", bob="user")
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in(api, "bob")
    # When
    response = await when_save_layout(api, public["id"], TABLE_ONLY, 1)
    # Then
    then_status_is(response, 200)
    assert response.json()["owner"] == public["owner"]
    assert response.json()["updated_by"]["id"] != public["owner"]["id"]
    then_body_includes(response, layout=TABLE_ONLY, revision=2)


@pytest.mark.parametrize(
    ("layout", "location"),
    [
        ({**DEFAULT_LAYOUT, "order": ["table", "table"]}, ["layout", "order"]),
        ({**DEFAULT_LAYOUT, "view": "grid"}, ["layout", "view"]),
        ({**DEFAULT_LAYOUT, "arrange": "row"}, ["layout", "arrange"]),
    ],
    ids=["order", "view", "arrange"],
)
async def test_invalid_layout_is_rejected_with_location(
    api: Api, layout: dict[str, object], location: list[str]
) -> None:
    """Scenario: 배치 값이 잘못되면 422 invalid-report(위치 layout.*)이고 저장되지 않는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본", layout=CHART_FIRST_SIDE)
    # When
    response = await when_save_layout(api, saved["id"], layout, 1)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    assert [e["location"] for e in response.json()["errors"]] == [location]
    await then_detail_layout_is(api, saved["id"], CHART_FIRST_SIDE, revision=1)


async def test_invalid_layout_on_create_is_rejected_and_not_saved(api: Api) -> None:
    """Scenario: 만들기에서 배치 값이 잘못되면 422 invalid-report이고 리포트가 생기지 않는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_report(
        api, report_body("잘못된 배치", layout={**DEFAULT_LAYOUT, "view": "x"})
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    assert [e["location"] for e in response.json()["errors"]] == [["layout", "view"]]


async def test_layout_with_an_unknown_key_is_a_request_validation_error(api: Api) -> None:
    """Scenario: 배치에 알 수 없는 키가 있으면 422 request-validation이다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본")
    # When
    response = await when_save_layout(api, saved["id"], {**DEFAULT_LAYOUT, "colour": "red"}, 1)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_layout_save_of_a_report_with_an_unreadable_definition_is_refused_untouched(
    api: Api,
) -> None:
    """Scenario: 정의가 깨진 리포트의 배치 저장은 422 stored-invalid이고 배치는 그대로다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "깨진 정의", layout=CHART_FIRST_SIDE)
    await given_stored_definition_is_unreadable(api, saved["id"])
    # When
    response = await when_save_layout(api, saved["id"], TABLE_ONLY, 1)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    assert [(e["location"], e["code"]) for e in response.json()["errors"]] == [
        (["definition"], "stored-invalid")
    ]
    reopened = await when_get_report(api, saved["id"])
    assert reopened.status_code == 422  # 정의를 읽을 수 없어 상세도 같은 오류다
