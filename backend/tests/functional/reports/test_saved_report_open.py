"""Feature: 조회한 리포트를 저장하고 목록에서 찾아 열면 저장된 정의로 최신 데이터를 다시 조회한다.

결과는 저장하지 않고 열 때마다 저장된 정의로 SQL을 다시 만들어 실행한다. 서버가 만든 SQL이 함께
저장되며 클라이언트가 SQL을 보낼 수는 없다.
(관련 단위 테스트: tests/unit/application/test_saved_report_*.py,
tests/unit/web/test_saved_report_*.py)
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.dashboard import given_dashboard_deal, given_today_is
from tests.functional.steps.forecast import given_sales_user
from tests.functional.steps.reports import (
    VENDOR_NAMES,
    VENDOR_QUARTER_BODY,
    VENDOR_QUARTER_DEALS,
)
from tests.functional.steps.saved_reports import (
    SIMPLE_DEFINITION,
    given_logged_in,
    given_query_body,
    given_saved_report,
    given_stored_definition_uses_legacy_formats,
    given_users,
    report_body,
    then_listed_ids_are,
    then_run_matches_query,
    when_get_report,
    when_list_reports,
    when_run_saved_report,
    when_save_report,
)
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
TODAY = date(2026, 10, 27)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _given_vendor_quarter_deals(api: Api) -> None:
    vendor_ids = {}
    for name in VENDOR_NAMES:
        vendor_ids[name] = (await given_vendor(api, name)).id
    owner = await given_sales_user(api, "kim")
    for vendor, day, forecast, amount in VENDOR_QUARTER_DEALS:
        await given_dashboard_deal(
            api,
            owner=owner,
            forecast=forecast,
            amount=amount,
            day=day,
            vendor_id=vendor_ids.get(vendor) if vendor else None,
        )


async def test_saved_report_reopens_with_the_same_result(api: Api) -> None:
    """Scenario: 조회한 정의를 저장하고 목록에서 찾아 열면 /query와 같은 행·합계가 나온다."""
    # Given
    await given_today_is(api, TODAY)
    await _given_vendor_quarter_deals(api)
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    queried = await given_query_body(api, VENDOR_QUARTER_BODY)
    saved = await given_saved_report(api, "Vendor별 분기 금액", definition=VENDOR_QUARTER_BODY)
    # When
    response = await when_run_saved_report(api, saved["id"])
    # Then
    then_run_matches_query(response, queried)
    then_listed_ids_are(await when_list_reports(api), [saved["id"]])


async def test_saved_report_runs_again_with_the_data_of_the_moment(api: Api) -> None:
    """Scenario: 저장 뒤 Deal이 늘면 같은 리포트를 다시 열 때 늘어난 데이터로 조회한다."""
    # Given
    await given_today_is(api, TODAY)
    await _given_vendor_quarter_deals(api)
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    before = await given_query_body(api, VENDOR_QUARTER_BODY)
    saved = await given_saved_report(api, "분기 금액", definition=VENDOR_QUARTER_BODY)
    await given_logged_in_as(api, role="admin")
    owner = await given_sales_user(api, "lee")
    await given_dashboard_deal(api, owner=owner, forecast="pipeline", amount=7777, day="2026-02-14")
    await given_logged_in(api, "alice")
    # When
    response = await when_run_saved_report(api, saved["id"])
    # Then
    then_status_is(response, 200)
    assert response.json()["total_count"] >= before["total_count"]
    assert response.json()["rows"] != before["rows"]
    after = await given_query_body(api, VENDOR_QUARTER_BODY)
    assert response.json()["rows"] == after["rows"]


async def test_saved_report_keeps_the_server_rendered_sql(api: Api) -> None:
    """Scenario: 저장 응답에는 서버가 정의로 만든 SQL이 들어 있고 열어도 같은 SQL이 나온다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_report(api, report_body("SQL 확인"))
    # Then
    then_status_is(response, 201)
    saved = response.json()
    assert saved["generated_sql"].lstrip().upper().startswith("SELECT")
    reopened = await when_get_report(api, saved["id"])
    assert reopened.json()["generated_sql"] == saved["generated_sql"]
    assert reopened.json()["definition"]["columns"][0]["field"] == "deal.code"


async def test_client_cannot_supply_the_sql(api: Api) -> None:
    """Scenario: 요청에 SQL을 넣으면 거절되고 저장되지 않는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_report(
        api, {**report_body("SQL 주입"), "generated_sql": "DROP TABLE"}
    )
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    then_listed_ids_are(await when_list_reports(api), [])


async def test_invalid_definition_is_not_saved(api: Api) -> None:
    """Scenario: 카탈로그에 없는 필드를 쓴 정의는 invalid-report이고 저장되지 않는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_report(
        api, report_body("잘못된 정의", definition={"columns": [{"field": "deal.password"}]})
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    assert [(e["location"], e["code"]) for e in response.json()["errors"]] == [
        (["columns", 0, "field"], "unknown-field")
    ]
    then_listed_ids_are(await when_list_reports(api), [])


@pytest.mark.parametrize(
    "overrides",
    [{"name": "  "}, {"name": "가" * 101}, {"description": "a" * 1001}, {"visibility": "all"}],
    ids=["blank-name", "long-name", "long-description", "unknown-visibility"],
)
async def test_invalid_name_description_or_visibility_is_not_saved(
    api: Api, overrides: dict[str, str]
) -> None:
    """Scenario: 이름·설명·공개 범위가 규칙을 어기면 invalid-value이고 저장되지 않는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    # When
    response = await when_save_report(api, report_body(**overrides))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_listed_ids_are(await when_list_reports(api), [])


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_can_save_a_report(api: Api, role: str) -> None:
    """Scenario: admin·sales·user 모두 리포트를 저장할 수 있다(201, 만든 사람은 자기 자신)."""
    # Given
    login_id = await given_logged_in_as(api, role=role)  # type: ignore[arg-type]
    # When
    response = await when_save_report(api, report_body("역할별"))
    # Then
    then_status_is(response, 201)
    assert response.headers["location"] == f"/api/v1/reports/{response.json()['id']}"
    assert response.json()["revision"] == 1
    assert response.json()["owner"]["id"] == response.json()["updated_by"]["id"]
    assert login_id


async def test_list_orders_by_last_update_and_shows_the_data_entities(api: Api) -> None:
    """Scenario: 목록은 최종 수정이 최근인 것부터 나오고 쓰인 데이터 엔티티가 붙는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    first = await given_saved_report(api, "먼저", definition=SIMPLE_DEFINITION)
    second = await given_saved_report(
        api,
        "나중",
        definition={
            "columns": [{"field": "deal.code"}, {"field": "action.type"}],
            "row_limit": 100,
        },
    )
    # When
    response = await when_list_reports(api)
    # Then
    then_listed_ids_are(response, [second["id"], first["id"]])
    assert [item["entities"] for item in response.json()] == [["deal", "action"], ["deal"]]


LEGACY_DEFINITION = {
    "columns": [
        {"field": "deal.name", "format": "as_is"},
        {"field": "deal.status", "format": "name"},
        {"field": "deal.forecast", "format": "key"},
        {"field": "deal.code", "format": "prefix", "prefix_length": 5},
    ],
    "conditions": [],
    "combine": "and",
    "sort": None,
    "row_limit": 100,
}
UPGRADED_DEFINITION = {
    "columns": [
        {"field": "deal.name"},
        {"field": "deal.status"},
        {"field": "deal.forecast"},
        {"field": "deal.code", "prefix_length": 5},
    ],
    "row_limit": 100,
}


async def test_saved_report_with_legacy_formats_opens_in_new_shape(api: Api) -> None:
    """Scenario: 예전 포맷으로 저장된 리포트를 열면 새 형식으로 보이고 코드 열은 이름으로 나온다."""
    # Given
    await given_today_is(api, TODAY)
    owner = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=owner, forecast="pipeline", amount=10, day="2026-02-14")
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "예전 포맷", definition=UPGRADED_DEFINITION)
    await given_stored_definition_uses_legacy_formats(api, saved["id"], LEGACY_DEFINITION)
    # When
    detail = await when_get_report(api, saved["id"])
    response = await when_run_saved_report(api, saved["id"])
    # Then
    then_status_is(detail, 200)
    columns = detail.json()["definition"]["columns"]
    assert [c["format"] for c in columns] == [None, None, None, None]
    assert [c["prefix_length"] for c in columns] == [None, None, None, 5]
    then_status_is(response, 200)
    status_value, forecast_value = response.json()["rows"][0][1:3]
    assert status_value != "prospecting"  # key가 아니라 표시 이름
    assert forecast_value != "pipeline"
    assert [c["format"] for c in response.json()["columns"]] == [None, None, None, None]


LEGACY_SORT_DEFINITION = {
    "columns": [
        {"field": "deal.name"},
        {"field": "deal.vendor"},
    ],
    "conditions": [],
    "combine": "and",
    "sort": {"column": 1, "direction": "desc"},
    "row_limit": 100,
}


async def test_saved_report_with_old_sort_opens_with_column_sort(api: Api) -> None:
    """Scenario: 예전 최상위 정렬로 저장된 리포트는 컬럼 정렬로 보이고 같은 순서로 실행된다."""
    # Given
    await given_today_is(api, TODAY)
    ibm = await given_vendor(api, "IBM")
    sap = await given_vendor(api, "SAP")
    owner = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=owner, name="Alpha", vendor_id=ibm.id)
    await given_dashboard_deal(api, owner=owner, name="Beta", vendor_id=sap.id)
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "예전 정렬", definition=SIMPLE_DEFINITION)
    await given_stored_definition_uses_legacy_formats(api, saved["id"], LEGACY_SORT_DEFINITION)
    # When
    detail = await when_get_report(api, saved["id"])
    response = await when_run_saved_report(api, saved["id"])
    # Then
    then_status_is(detail, 200)
    definition = detail.json()["definition"]
    assert [c["sort"] for c in definition["columns"]] == [None, "desc"]
    assert "sort" not in definition
    then_status_is(response, 200)
    assert response.json()["rows"] == [["Beta", "SAP"], ["Alpha", "IBM"]]
