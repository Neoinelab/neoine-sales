"""Feature: Dashboard의 모든 숫자는 Drill-down으로 여는 Deal 목록(원장)과 일치한다(9장 정합성).

각 타일·막대·표 행을 누르면 열리는 Deal 목록 조건(Forecast 구분 `forecast_outcome` 포함)으로
센 건수와 revenue_amount 합이 대시보드가 보여 준 숫자와 같다. 기간 밖 Expected Close의 Deal은
어느 쪽에서도 기간 집계에 들어가지 않는다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.dashboard import (
    given_dashboard_deal,
    given_today_is,
    then_every_drilldown_matches_the_ledger,
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


@pytest.mark.parametrize(
    ("by_quarter", "by_owner", "by_vendor"),
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, True, True),
        (False, False, True),
    ],
    ids=["year", "year-quarter", "quarter-owner", "quarter-owner-vendor", "year-vendor"],
)
async def test_every_drilldown_matches_deal_list_ledger(
    api: Api, by_quarter: bool, by_owner: bool, by_vendor: bool
) -> None:
    """Scenario: 여러 조건 조합에서 모든 요소의 숫자가 같은 조건 Deal 목록의 건수·금액과 같다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    sap = await given_vendor(api, "SAP")
    oracle = await given_vendor(api, "Oracle")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    for owner, status, forecast, amount, day, vendor_id in (
        (kim, None, "pipeline", 10, "2026-01-01", sap.id),
        (kim, "introduction", "best", 20, "2026-03-31", None),
        (kim, "poc_completed", "commit", 30, "2026-04-01", sap.id),
        (lee, None, "most_likely", 40, "2026-10-05", sap.id),
        (lee, "price_negotiation", "lost", 50, "2026-10-10", sap.id),
        (lee, None, "won", 60, "2026-12-31", oracle.id),
        (kim, None, "pipeline", 70, "2026-11-15", sap.id),
        (kim, "technical_evaluation", "commit", 80, "2026-11-30", None),
        (lee, None, "pipeline", 90, "2025-12-31", sap.id),
        (lee, None, "pipeline", 100, "2027-01-01", sap.id),
    ):
        await given_dashboard_deal(
            api,
            owner=owner,
            status=status,
            forecast=forecast,
            amount=amount,
            day=day,
            vendor_id=vendor_id,
        )
    conditions: dict[str, int] = {"year": 2026}
    if by_quarter:
        conditions["quarter"] = 4
    if by_owner:
        conditions["owner_user_id"] = kim
    if by_vendor:
        conditions["vendor_id"] = sap.id
    # When
    response = await when_get_dashboard_summary(api, **conditions)
    # Then
    then_status_is(response, 200)
    await then_every_drilldown_matches_the_ledger(api, response, **conditions)
