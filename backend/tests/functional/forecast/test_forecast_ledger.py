"""Feature: Forecast 요약 합계는 같은 조건의 Deal 목록(원장)과 항상 일치한다(검수 4, 9장).

요약의 Open 합 + Won 셀 = 같은 조건 `/deals`에서 Lost를 뺀 건수·금액의 합.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_status_is
from tests.functional.steps.forecast import (
    conditions_of,
    given_forecast_deal,
    given_sales_user,
    then_ledger_matches,
    when_get_summary,
)
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("year", "quarter", "month", "by_owner", "by_vendor"),
    [
        (2026, None, None, False, False),
        (2026, 4, None, False, False),
        (2026, None, 11, False, False),
        (2027, None, 1, False, False),
        (2026, 4, None, False, True),
        (2026, 4, None, True, False),
        (2026, None, 11, True, True),
    ],
    ids=["year", "quarter", "month", "next-january", "vendor", "owner", "month-owner-vendor"],
)
async def test_summary_total_matches_deal_list_ledger(  # noqa: PLR0913, PLR0917 - 조건 조합
    api: Api,
    year: int,
    quarter: int | None,
    month: int | None,
    by_owner: bool,
    by_vendor: bool,
) -> None:
    """Scenario: 여러 조건 조합에서 요약 합계와 Deal 목록 원장의 건수·금액이 같다."""
    # Given
    sap = await given_vendor(api, "SAP")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    for owner, forecast, amount, day, vendor_id in (
        (kim, "pipeline", 10, "2026-10-01", sap.id),
        (kim, "commit", 20, "2026-11-30", None),
        (kim, "lost", 30, "2026-11-10", sap.id),
        (lee, "best", 40, "2026-11-05", sap.id),
        (lee, "won", 50, "2026-12-31", None),
        (lee, "most_likely", 60, "2027-01-01", sap.id),
        (kim, "pipeline", 70, "2026-03-15", None),
    ):
        await given_forecast_deal(
            api, owner=owner, forecast=forecast, amount=amount, day=day, vendor_id=vendor_id
        )
    conditions = conditions_of(
        year=year,
        quarter=quarter,
        month=month,
        owner_user_id=kim if by_owner else None,
        vendor_id=sap.id if by_vendor else None,
    )
    # When
    response = await when_get_summary(api, **conditions)
    # Then
    then_status_is(response, 200)
    await then_ledger_matches(api, response, **conditions)
