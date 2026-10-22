"""Feature: Dashboard 주의 필요 Deal 타일은 기간을 무시하고 담당자·Vendor만 적용한다.

기한초과·미업데이트 수는 같은 담당자·Vendor 조건의 Deal 목록(`overdue=true`·`stale=true`)
total과 같고, 미업데이트 일수는 경고 기준 값(기본 14)이다. 이번 달·이번 분기 Expected Close는
서버 업무 날짜 기준의 Open Deal(Won·Lost 제외)만 센다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action
from tests.functional.steps.alerts import then_stale_days_is
from tests.functional.steps.auth import ADMIN_LOGIN, given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.dashboard import (
    given_dashboard_deal,
    given_today_is,
    when_get_dashboard_summary,
)
from tests.functional.steps.deal_list_risk import given_deals_with_every_risk
from tests.functional.steps.deal_risk import given_due_in
from tests.functional.steps.deals import given_my_user_id, when_list_deals
from tests.functional.steps.forecast import given_sales_user
from tests.functional.steps.users import log_in

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def test_attention_counts_ignore_period_and_follow_owner_vendor(api: Api) -> None:
    """Scenario: 기한초과·미업데이트 수는 기간을 무시하고 같은 담당자 Deal 목록 total과 같다."""
    # Given
    await given_deals_with_every_risk(
        api
    )  # 경고 기준 7일, 영업 사용자가 만든 위험 Deal 4건(+Lost 1건)
    sales_id = await given_my_user_id(api)
    await log_in(api, ADMIN_LOGIN)
    lee = await given_sales_user(api, "lee")
    other = await given_dashboard_deal(api, owner=lee, day="2024-05-01")
    await log_in(api, "lee")
    await given_action(api, str(other["code"]), due_date=given_due_in(api, -1))
    await log_in(api, ADMIN_LOGIN)
    # When
    everyone = await when_get_dashboard_summary(api, year=2020, quarter=1)
    mine = await when_get_dashboard_summary(api, year=2020, quarter=1, owner_user_id=sales_id)
    # Then
    then_status_is(everyone, 200)
    then_status_is(mine, 200)
    overdue_all = await when_list_deals(api, overdue="true")
    stale_all = await when_list_deals(api, stale="true")
    overdue_mine = await when_list_deals(api, overdue="true", owner_user_id=sales_id)
    stale_mine = await when_list_deals(api, stale="true", owner_user_id=sales_id)
    assert everyone.json()["attention"]["overdue"] == overdue_all.json()["total"] > 0
    assert everyone.json()["attention"]["stale"] == stale_all.json()["total"] > 0
    assert mine.json()["attention"]["overdue"] == overdue_mine.json()["total"]
    assert mine.json()["attention"]["stale"] == stale_mine.json()["total"]
    assert mine.json()["attention"]["overdue"] < everyone.json()["attention"]["overdue"]


async def test_attention_reports_the_saved_stale_days(api: Api) -> None:
    """Scenario: stale_days는 admin이 저장한 경고 기준이다."""
    # Given
    await given_deals_with_every_risk(api)  # 경고 기준을 7일로 저장한다
    await log_in(api, ADMIN_LOGIN)
    # When
    response = await when_get_dashboard_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    assert response.json()["attention"]["stale_days"] == 7
    await then_stale_days_is(api, 7)


async def test_attention_uses_the_default_stale_days_when_nothing_is_saved(api: Api) -> None:
    """Scenario: 경고 기준을 저장한 적이 없으면 stale_days는 14이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_dashboard_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    assert response.json()["attention"]["stale_days"] == 14


async def test_closing_counts_use_business_date_month_and_quarter(api: Api) -> None:
    """Scenario: 오늘이 2026-10-23이면 이번 달은 10월 Open Deal, 이번 분기는 Q4 Open Deal만 센다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=kim, forecast="pipeline", day="2026-10-05")
    await given_dashboard_deal(api, owner=kim, forecast="won", day="2026-10-30")
    await given_dashboard_deal(api, owner=kim, forecast="lost", day="2026-10-10")
    await given_dashboard_deal(api, owner=kim, forecast="commit", day="2026-11-15")
    await given_dashboard_deal(api, owner=kim, forecast="best", day="2026-12-20")
    await given_dashboard_deal(api, owner=kim, forecast="pipeline", day="2026-09-30")
    await given_dashboard_deal(api, owner=kim, forecast="pipeline", day="2027-01-01")
    # When
    response = await when_get_dashboard_summary(api, year=2020)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["today"] == "2026-10-23"
    assert body["attention"]["closing_this_month"] == {"year": 2026, "month": 10, "count": 1}
    assert body["attention"]["closing_this_quarter"] == {"year": 2026, "quarter": 4, "count": 3}


@pytest.mark.parametrize(
    ("today", "expected_month", "expected_quarter"),
    [
        (date(2026, 12, 31), {"year": 2026, "month": 12}, {"year": 2026, "quarter": 4}),
        (date(2027, 1, 1), {"year": 2027, "month": 1}, {"year": 2027, "quarter": 1}),
    ],
    ids=["dec31", "jan1"],
)
async def test_this_month_and_quarter_switch_on_the_business_date_boundary(
    api: Api, today: date, expected_month: dict[str, int], expected_quarter: dict[str, int]
) -> None:
    """Scenario: 12-31은 2026 Q4·12월, 01-01은 2027 Q1·1월로 바뀌고 해당 Deal을 센다."""
    # Given
    await given_today_is(api, today)
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=kim, forecast="pipeline", day="2026-12-31")
    await given_dashboard_deal(api, owner=kim, forecast="pipeline", day="2027-01-01")
    # When
    response = await when_get_dashboard_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    attention = response.json()["attention"]
    assert attention["closing_this_month"] == {**expected_month, "count": 1}
    assert attention["closing_this_quarter"] == {**expected_quarter, "count": 1}


async def test_closing_counts_follow_owner_and_vendor(api: Api) -> None:
    """Scenario: 담당자를 고르면 이번 달·이번 분기 Expected Close도 그 담당자 Deal만 센다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    await given_dashboard_deal(api, owner=kim, day="2026-10-05")
    await given_dashboard_deal(api, owner=lee, day="2026-10-06")
    await given_dashboard_deal(api, owner=lee, day="2026-11-06")
    # When
    response = await when_get_dashboard_summary(api, year=2026, owner_user_id=lee)
    # Then
    then_status_is(response, 200)
    attention = response.json()["attention"]
    assert attention["closing_this_month"]["count"] == 1
    assert attention["closing_this_quarter"]["count"] == 2
