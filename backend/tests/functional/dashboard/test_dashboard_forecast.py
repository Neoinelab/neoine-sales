"""Feature: Dashboard의 Forecast 타일과 분기별 Closing 막대는 Forecast 화면 숫자와 같다.

상단 Forecast 타일은 같은 조건의 `GET /forecast/summary` total과 같고(Lost 제외, 추가된 Open
코드 포함), 분기 막대는 Quarter 필터와 관계없이 선택 연도의 Q1~Q4 4개이며 각 분기가 그 분기
Forecast 요약 total과 같다.
"""

from datetime import date
from typing import TYPE_CHECKING, cast

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import given_code_created
from tests.functional.steps.common import then_status_is
from tests.functional.steps.dashboard import (
    cells_by_key,
    given_dashboard_deal,
    given_today_is,
    then_forecast_column_keys_are,
    then_forecast_part_equals_forecast_summary,
    then_quarters_match_forecast_summary,
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
    [(False, False, False), (True, False, False), (True, True, False), (True, True, True)],
    ids=["year", "quarter", "quarter-owner", "quarter-owner-vendor"],
)
async def test_forecast_tiles_equal_forecast_summary_total(
    api: Api, by_quarter: bool, by_owner: bool, by_vendor: bool
) -> None:
    """Scenario: 같은 조건의 두 API에서 Forecast 타일의 열·셀·open_total이 요약 total과 같다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
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
        (kim, "pipeline", 70, "2026-03-15", sap.id),
    ):
        await given_dashboard_deal(
            api, owner=owner, forecast=forecast, amount=amount, day=day, vendor_id=vendor_id
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
    await then_forecast_part_equals_forecast_summary(api, response, **conditions)
    then_forecast_column_keys_are(response, ["pipeline", "best", "most_likely", "commit", "won"])


async def test_forecast_tiles_include_a_forecast_code_added_by_admin(api: Api) -> None:
    """Scenario: admin이 추가한 Open 코드가 타일 열이 되고 그 Deal이 Open 합계에 든다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    added = await given_code_created(api, kind="forecast", name="Verbal")
    key = cast("str", added["key"])
    await given_dashboard_deal(api, owner=kim, forecast=key, amount=70, day="2026-11-01")
    await given_dashboard_deal(api, owner=kim, forecast="pipeline", amount=5, day="2026-11-02")
    # When
    response = await when_get_dashboard_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    forecasts = response.json()["forecasts"]
    assert [c["key"] for c in forecasts["columns"]][-1] != "lost"
    assert key in [c["key"] for c in forecasts["columns"]]
    assert cells_by_key(forecasts["cells"])[key] == (1, 70)
    assert (forecasts["open_total"]["count"], forecasts["open_total"]["amount"]) == (2, 75)
    await then_forecast_part_equals_forecast_summary(api, response, year=2026)


async def test_quarters_cover_whole_year_even_with_quarter_filter(api: Api) -> None:
    """Scenario: Quarter 필터와 무관하게 quarters는 4개이고 각 분기가 분기별 요약 total과 같다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    for forecast, amount, day in (
        ("pipeline", 1, "2026-01-01"),
        ("commit", 2, "2026-03-31"),
        ("best", 4, "2026-04-01"),
        ("won", 8, "2026-06-30"),
        ("most_likely", 16, "2026-07-01"),
        ("lost", 32, "2026-09-30"),
        ("commit", 64, "2026-10-01"),
        ("won", 128, "2026-12-31"),
        ("pipeline", 256, "2027-01-01"),
    ):
        await given_dashboard_deal(api, owner=kim, forecast=forecast, amount=amount, day=day)
    # When
    response = await when_get_dashboard_summary(api, year=2026, quarter=2)
    # Then
    then_status_is(response, 200)
    await then_quarters_match_forecast_summary(api, response, year=2026)
    assert [(q["from"], q["to"]) for q in response.json()["quarters"]] == [
        ("2026-01-01", "2026-03-31"),
        ("2026-04-01", "2026-06-30"),
        ("2026-07-01", "2026-09-30"),
        ("2026-10-01", "2026-12-31"),
    ]


async def test_quarters_follow_owner_and_vendor_filters(api: Api) -> None:
    """Scenario: 담당자·Vendor를 고르면 분기 막대도 그 조건만 센다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    sap = await given_vendor(api, "SAP")
    kim = await given_sales_user(api, "kim")
    lee = await given_sales_user(api, "lee")
    for owner, forecast, amount, day, vendor_id in (
        (kim, "pipeline", 1, "2026-02-01", sap.id),
        (kim, "commit", 2, "2026-05-01", None),
        (lee, "best", 4, "2026-08-01", sap.id),
        (kim, "won", 8, "2026-11-01", sap.id),
    ):
        await given_dashboard_deal(
            api, owner=owner, forecast=forecast, amount=amount, day=day, vendor_id=vendor_id
        )
    # When
    response = await when_get_dashboard_summary(api, year=2026, owner_user_id=kim, vendor_id=sap.id)
    # Then
    then_status_is(response, 200)
    await then_quarters_match_forecast_summary(
        api, response, year=2026, owner_user_id=kim, vendor_id=sap.id
    )
