"""Feature: Dashboard Status 탭은 Status별 건수·금액을 Expected Close 기준 기간 안에서 보여 준다.

Lost Deal(Forecast)은 진행 중 파이프라인이 아니므로 빠지고 Won(계약완료)은 포함된다.
기간 밖 Deal은 기간 집계에 들어가지 않는다. 모든 Status 코드가 order 순으로 나오고
Deal이 없는 Status는 0건·0원이다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.dashboard import (
    given_dashboard_deal,
    given_today_is,
    then_status_items_are,
    then_status_total_is,
    when_get_dashboard_summary,
)
from tests.functional.steps.forecast import given_sales_user
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def test_status_pipeline_counts_and_amounts_by_status(api: Api) -> None:
    """Scenario: 올해 Status별 합계에서 Lost·기간 밖 Deal은 빠지고 계약완료는 든다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=kim, forecast="pipeline", amount=100, day="2026-03-01")
    await given_dashboard_deal(api, owner=kim, forecast="best", amount=50, day="2026-05-01")
    await given_dashboard_deal(
        api, owner=kim, status="poc_completed", forecast="commit", amount=200, day="2026-07-01"
    )
    await given_dashboard_deal(api, owner=kim, forecast="won", amount=300, day="2026-12-31")
    await given_dashboard_deal(
        api, owner=kim, status="price_negotiation", forecast="lost", amount=400, day="2026-10-10"
    )
    await given_dashboard_deal(api, owner=kim, amount=7, day="2025-12-31")
    await given_dashboard_deal(api, owner=kim, amount=9, day="2027-01-01")
    # When
    response = await when_get_dashboard_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    then_status_items_are(
        response,
        {
            "prospecting": (2, 150),
            "poc_completed": (1, 200),
            "contract_completed": (1, 300),
        },
    )
    then_status_total_is(response, (4, 650))


async def test_status_pipeline_is_all_zero_when_no_deal_matches(api: Api) -> None:
    """Scenario: 조건에 맞는 Deal이 없으면 모든 Status가 0건·0원이고 합계도 0이다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_dashboard_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    then_status_items_are(response, {})
    then_status_total_is(response, (0, 0))


async def test_status_pipeline_follows_quarter_owner_and_vendor(api: Api) -> None:
    """Scenario: Quarter·담당자·Vendor를 고르면 그 조건의 Deal만 Status별로 센다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    sap = await given_vendor(api, "SAP")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    await given_dashboard_deal(api, owner=kim, amount=1, day="2026-02-01", vendor_id=sap.id)
    await given_dashboard_deal(api, owner=kim, amount=2, day="2026-02-02")
    await given_dashboard_deal(api, owner=lee, amount=4, day="2026-02-03", vendor_id=sap.id)
    await given_dashboard_deal(api, owner=kim, amount=8, day="2026-11-01", vendor_id=sap.id)
    # When
    response = await when_get_dashboard_summary(
        api, year=2026, quarter=1, owner_user_id=kim, vendor_id=sap.id
    )
    # Then
    then_status_is(response, 200)
    then_status_items_are(response, {"prospecting": (1, 1)})
    then_status_total_is(response, (1, 1))


@pytest.mark.parametrize(
    ("deal_day", "year", "quarter", "count"),
    [
        ("2026-12-31", 2026, None, 1),
        ("2026-12-31", 2026, 4, 1),
        ("2027-01-01", 2026, None, 0),
        ("2027-01-01", 2027, 1, 1),
        ("2026-03-31", 2026, 1, 1),
        ("2026-04-01", 2026, 1, 0),
    ],
    ids=["dec31-year", "dec31-q4", "jan1-prev-year", "jan1-q1", "mar31-q1", "apr1-not-q1"],
)
async def test_period_boundaries_are_inclusive_by_expected_close(
    api: Api, deal_day: str, year: int, quarter: int | None, count: int
) -> None:
    """Scenario: Expected Close가 분기·연의 마지막 날과 첫 날이면 그 기간에 들어간다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_dashboard_deal(api, owner=kim, amount=5, day=deal_day)
    params: dict[str, int] = {"year": year}
    if quarter is not None:
        params["quarter"] = quarter
    # When
    response = await when_get_dashboard_summary(api, **params)
    # Then
    then_status_is(response, 200)
    then_status_total_is(response, (count, 5 * count))
