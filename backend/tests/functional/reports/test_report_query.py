"""Feature: 로그인한 모든 역할이 리포트 필드 목록을 보고, 정의대로 Deal·Action을 조회한다.

서버는 허용 필드 목록과 바인딩 파라미터로만 SQL을 만들고, 결과는 Deals 목록과 같은 숫자다.
(관련 단위·계약 테스트: tests/unit/repositories/test_report_query_*_contract.py)
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_types import given_type_id
from tests.functional.steps.actions import given_action
from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.dashboard import given_dashboard_deal, given_today_is
from tests.functional.steps.forecast import given_sales_user
from tests.functional.steps.reports import (
    VENDOR_NAMES,
    VENDOR_QUARTER_BODY,
    VENDOR_QUARTER_DEALS,
    then_fields_are_listed,
    then_report_error_locations_are,
    then_rows_are,
    then_vendor_quarter_cells_match_the_deal_list,
    when_get_report_fields,
    when_query_report,
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


async def test_vendor_quarter_report_matches_the_deal_list(api: Api) -> None:
    """Scenario: Vendor x 분기 금액 합계(Lost 제외, 올해)가 Deals 목록의 같은 조건 숫자와 같다."""
    # Given
    await given_today_is(api, TODAY)
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
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_query_report(api, VENDOR_QUARTER_BODY)
    # Then
    then_status_is(response, 200)
    await then_vendor_quarter_cells_match_the_deal_list(api, response, vendor_ids)


async def test_read_only_user_can_read_the_field_list(api: Api) -> None:
    """Scenario: 읽기 전용(user) 역할도 필드 카탈로그를 받는다."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_get_report_fields(api)
    # Then
    then_fields_are_listed(response, count=40)


async def test_read_only_user_can_query_a_report(api: Api) -> None:
    """Scenario: 읽기 전용(user) 역할도 리포트를 조회한다(쓰기 권한이 필요 없다)."""
    # Given
    await given_today_is(api, TODAY)
    owner = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=owner, amount=7, day="2026-11-15", name="Visible")
    await given_logged_in_as(api, role="user")
    # When
    response = await when_query_report(api, {"columns": [{"field": "deal.name"}]})
    # Then
    then_rows_are(response, [["Visible"]])


async def test_anonymous_user_cannot_use_reports(api: Api) -> None:
    """Scenario: 로그인하지 않으면 리포트 조회는 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_query_report(api, {"columns": [{"field": "deal.name"}]})
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_unknown_field_and_operator_are_rejected(api: Api) -> None:
    """Scenario: 허용 목록 밖 필드와 맞지 않는 연산자는 위치와 함께 422로 거절된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    body = {
        "columns": [{"field": "deal.code"}, {"field": "deal.password"}],
        "conditions": [{"field": "deal.name", "operator": "gt", "value": "x"}],
    }
    # When
    response = await when_query_report(api, body)
    # Then
    then_report_error_locations_are(
        response,
        [
            (["columns", 1, "field"], "unknown-field"),
            (["conditions", 0, "operator"], "operator-not-allowed"),
        ],
    )


async def test_grouped_text_column_without_aggregate_is_rejected(api: Api) -> None:
    """Scenario: 그룹핑 리포트의 텍스트 컬럼에 집계가 없으면 422 aggregate-required다."""
    # Given
    await given_logged_in_as(api, role="sales")
    body = {"columns": [{"field": "deal.vendor", "group": True}, {"field": "deal.code"}]}
    # When
    response = await when_query_report(api, body)
    # Then
    then_report_error_locations_are(response, [(["columns", 1, "aggregate"], "aggregate-required")])


async def test_action_rows_sum_deal_amount_once(api: Api) -> None:
    """Scenario: Action 3건인 Deal의 금액 합계는 Deal 금액 그대로이고 Action 건수는 3이다."""
    # Given
    await given_today_is(api, TODAY)
    sap = await given_vendor(api, "SAP")
    owner = await given_sales_user(api, "kim")
    deal = await given_dashboard_deal(
        api, owner=owner, amount=100_000_000, day="2026-11-15", vendor_id=sap.id
    )
    for text in ("a1", "a2", "a3"):
        await given_action(api, deal["code"], action=text)
    body = {
        "columns": [
            {"field": "deal.vendor", "group": True},
            {"field": "deal.amount", "aggregate": "sum"},
            {"field": "action.count"},
        ]
    }
    # When
    response = await when_query_report(api, body)
    # Then
    then_rows_are(response, [["SAP", 100_000_000, 3]])
    assert response.json()["row_scope"] == "action"
    assert response.json()["deal_numbers_once"] is True


async def test_action_condition_only_returns_each_deal_once(api: Api) -> None:
    """Scenario: Action이 조건에만 있으면 행은 Deal 1건이고 맞는 Action이 없는 Deal은 빠진다."""
    # Given
    await given_today_is(api, TODAY)
    owner = await given_sales_user(api, "kim")
    with_meetings = await given_dashboard_deal(api, owner=owner, name="Met")
    await given_dashboard_deal(api, owner=owner, name="Never")
    for text in ("m1", "m2"):
        await given_action(api, with_meetings["code"], action=text, action_type="미팅")
    meeting = await given_type_id(api, "미팅")
    body = {
        "columns": [{"field": "deal.name"}],
        "conditions": [{"field": "action.type", "operator": "in", "value": [meeting]}],
    }
    # When
    response = await when_query_report(api, body)
    # Then
    then_rows_are(response, [["Met"]])
    assert response.json()["row_scope"] == "deal"
    assert response.json()["action_filter"] == "exists"


async def test_relative_period_follows_the_server_business_date(api: Api) -> None:
    """Scenario: '이번 달' 조건은 서버 업무 날짜(2026-10-27)의 10월 Expected Close만 고른다."""
    # Given
    await given_today_is(api, TODAY)
    owner = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=owner, name="October", day="2026-10-31")
    await given_dashboard_deal(api, owner=owner, name="November", day="2026-11-01")
    body = {
        "columns": [{"field": "deal.name"}],
        "conditions": [
            {
                "field": "deal.expected_close",
                "operator": "relative",
                "value": {"period": "this_month"},
            }
        ],
    }
    # When
    response = await when_query_report(api, body)
    # Then
    then_rows_are(response, [["October"]])
    assert response.json()["today"] == "2026-10-27"


async def test_grouped_report_returns_totals_beside_the_groups(api: Api) -> None:
    """Scenario: 그룹핑 리포트는 같은 조건의 합계(totals)를 그룹 행과 함께 돌려준다."""
    # Given
    await given_today_is(api, TODAY)
    sap = await given_vendor(api, "SAP")
    ibm = await given_vendor(api, "IBM")
    owner = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=owner, amount=10, vendor_id=sap.id)
    await given_dashboard_deal(api, owner=owner, amount=30, vendor_id=ibm.id)
    body = {
        "columns": [
            {"field": "deal.vendor", "group": True},
            {"field": "deal.amount", "aggregate": "sum"},
        ],
        "sort": {"column": 0, "direction": "asc"},
    }
    # When
    response = await when_query_report(api, body)
    # Then
    then_rows_are(response, [["IBM", 30], ["SAP", 10]])
    assert response.json()["totals"] == [None, 40]


async def test_values_that_look_like_sql_are_matched_as_text(api: Api) -> None:
    """Scenario: SQL처럼 보이는 검색어는 글자 그대로 찾고 데이터는 그대로다."""
    # Given
    await given_today_is(api, TODAY)
    owner = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=owner, name="Safe")
    body = {
        "columns": [{"field": "deal.name"}],
        "conditions": [
            {"field": "deal.name", "operator": "contains", "value": "'; drop table deals; --"}
        ],
    }
    # When
    response = await when_query_report(api, body)
    # Then
    then_rows_are(response, [])
    again = await when_query_report(api, {"columns": [{"field": "deal.name"}]})
    then_rows_are(again, [["Safe"]])
