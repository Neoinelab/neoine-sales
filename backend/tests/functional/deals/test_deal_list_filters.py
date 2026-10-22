"""Feature: 영업은 목록을 vendor_id·solution_id·forecast·연/분기로 좁혀 Deal을 찾는다.

연/분기는 Expected Close 기준이고 양끝을 포함한다(12-31은 Q4, 01-01은 Q1). 연/분기와
최종 업데이트 기간은 AND이고, quarter만 주면 서버 업무 날짜의 올해 분기다.
BANT Label 조건(bant_*)은 폐지되어 보내면 422다.
모든 필터는 서로 AND로 결합하고 total은 페이지와 무관하다.
"""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_lists import (
    then_codes_are,
    then_codes_are_exactly,
    then_total_is,
)
from tests.functional.steps.deal_risk import given_days_pass
from tests.functional.steps.deals import (
    given_clock_at,
    given_deal,
    when_list_deals,
)
from tests.functional.steps.updated_period import days_from_today
from tests.functional.steps.vendors import given_vendor
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_list_filters_by_vendor_and_solution_ids(api: Api) -> None:
    """Scenario: vendor_id·solution_id는 id가 같은 Deal만 거른다(AC-16)."""
    # Given
    sap = await given_vendor(api, "SAP", ["S/4HANA", "BW"])
    oracle = await given_vendor(api, "Oracle", ["EBS"])
    await given_logged_in_as(api, role="sales")
    erp = await given_deal(
        api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"], forecast_key="commit"
    )
    bw = await given_deal(api, vendor_id=sap.id, solution_id=sap.solutions["BW"])
    await given_deal(api, vendor_id=oracle.id, solution_id=oracle.solutions["EBS"])
    await given_deal(api)
    # When
    by_vendor = await when_list_deals(api, vendor_id=sap.id)
    by_solution = await when_list_deals(api, solution_id=sap.solutions["S/4HANA"])
    combined = await when_list_deals(
        api, vendor_id=sap.id, solution_id=sap.solutions["S/4HANA"], forecast_key="commit"
    )
    # Then
    then_codes_are_exactly(by_vendor, [erp["code"], bw["code"]])
    then_codes_are(by_solution, [erp["code"]])
    then_codes_are(combined, [erp["code"]])
    then_total_is(combined, 1)


async def test_unknown_vendor_id_lists_nothing(api: Api) -> None:
    """Scenario: 없는 vendor_id·solution_id는 422가 아니라 0건이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    # When
    by_vendor = await when_list_deals(api, vendor_id=MISSING_ID)
    by_solution = await when_list_deals(api, solution_id=MISSING_ID)
    # Then
    for response in (by_vendor, by_solution):
        then_status_is(response, 200)
        then_total_is(response, 0)


async def test_forecast_filter_matches_the_same_key(api: Api) -> None:
    """Scenario: forecast는 같은 key인 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    hit = await given_deal(api, forecast_key="commit")
    await given_deal(api, forecast_key="pipeline")
    # When
    response = await when_list_deals(api, forecast_key="commit")
    # Then
    then_status_is(response, 200)
    then_codes_are(response, [hit["code"]])
    then_total_is(response, 1)


async def test_an_unknown_forecast_key_gives_an_empty_list_not_an_error(api: Api) -> None:
    """Scenario: 없는 forecast key는 오류 없이 0건이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    # When
    response = await when_list_deals(api, forecast_key="no_such_forecast")
    # Then
    then_status_is(response, 200)
    then_codes_are(response, [])
    then_total_is(response, 0)


async def test_year_and_quarter_follow_the_expected_close_with_inclusive_boundaries(
    api: Api,
) -> None:
    """Scenario: 연/분기는 Expected Close 기준이고 분기의 첫날과 마지막 날을 포함한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    days = {
        "q1_last": "2026-03-31",
        "q2_first": "2026-04-01",
        "q2_last": "2026-06-30",
        "q3_first": "2026-07-01",
        "q4_last": "2026-12-31",
        "next_year": "2027-01-01",
    }
    deals = {name: await given_deal(api, revenue_date=day) for name, day in days.items()}
    # When
    quarter = await when_list_deals(api, year=2026, quarter=2)
    whole_year = await when_list_deals(api, year=2026)
    # Then
    then_codes_are_exactly(quarter, [deals["q2_first"]["code"], deals["q2_last"]["code"]])
    then_codes_are_exactly(
        whole_year,
        [deals[n]["code"] for n in ("q1_last", "q2_first", "q2_last", "q3_first", "q4_last")],
    )
    then_total_is(whole_year, 5)


async def test_year_and_quarter_are_combined_with_the_updated_period(api: Api) -> None:
    """Scenario: 연/분기(Expected Close)와 최종 업데이트 기간을 함께 주면 둘 다 만족해야 한다."""
    # Given
    login_id = await given_logged_in_as(api, role="sales")
    await given_deal(api, revenue_date="2026-05-10")  # 분기 안, 30일 전 등록(기간 밖)
    await given_days_pass(api, 30, login_id=login_id)
    inside = await given_deal(api, revenue_date="2026-05-20")
    await given_deal(api, revenue_date="2026-08-01")  # 분기 밖
    # When
    response = await when_list_deals(
        api, year=2026, quarter=2, updated_from=days_from_today(api, -14)
    )
    # Then
    then_codes_are(response, [inside["code"]])


async def test_quarter_alone_lists_this_years_quarter(api: Api) -> None:
    """Scenario: quarter만 주면 서버 업무 날짜의 올해 분기 Deal만 나온다(AC-19)."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_clock_at(api, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    this_year_q2 = await given_deal(api, revenue_date="2026-05-20")
    await given_deal(api, revenue_date="2025-05-20")
    await given_deal(api, revenue_date="2026-08-20")
    # When
    response = await when_list_deals(api, quarter=2)
    # Then
    then_status_is(response, 200)
    then_codes_are(response, [this_year_q2["code"]])
    then_total_is(response, 1)


async def test_quarter_with_a_year_uses_that_year(api: Api) -> None:
    """Scenario: year와 quarter를 함께 주면 그 해의 분기다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_clock_at(api, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    await given_deal(api, revenue_date="2026-05-20")
    past = await given_deal(api, revenue_date="2025-05-20")
    # When
    response = await when_list_deals(api, year=2025, quarter=2)
    # Then
    then_codes_are(response, [past["code"]])


@pytest.mark.parametrize(
    ("quarter", "first", "last"),
    [
        (1, "2026-01-01", "2026-03-31"),
        (2, "2026-04-01", "2026-06-30"),
        (3, "2026-07-01", "2026-09-30"),
        (4, "2026-10-01", "2026-12-31"),
    ],
)
async def test_quarter_alone_includes_both_ends_of_the_quarter(
    api: Api, quarter: int, first: str, last: str
) -> None:
    """Scenario: 분기는 첫날과 마지막 날을 포함하고 이웃 분기의 날은 제외한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_clock_at(api, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    first_deal = await given_deal(api, revenue_date=first)
    last_deal = await given_deal(api, revenue_date=last)
    outside_before = date.fromisoformat(first) - timedelta(days=1)
    outside_after = date.fromisoformat(last) + timedelta(days=1)
    await given_deal(api, revenue_date=outside_before.isoformat())
    await given_deal(api, revenue_date=outside_after.isoformat())
    # When
    response = await when_list_deals(api, quarter=quarter)
    # Then
    then_codes_are_exactly(response, [first_deal["code"], last_deal["code"]])


@pytest.mark.parametrize("params", [{"year": 2026, "quarter": 0}, {"year": 2026, "quarter": 5}])
async def test_a_quarter_outside_one_to_four_is_rejected(api: Api, params: dict[str, int]) -> None:
    """Scenario: quarter가 1~4 밖이면 422이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, **params)
    # Then
    then_status_is(response, 422)


@pytest.mark.parametrize("param", ["bant_budget", "bant_authority", "bant_need", "bant_timeline"])
async def test_bant_parameters_are_no_longer_accepted(api: Api, param: str) -> None:
    """Scenario: 폐지된 bant_* 조건을 보내면 조용히 무시하지 않고 request-validation 422이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    # When
    response = await when_list_deals(api, **{param: MISSING_ID})
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_all_filters_are_combined_and_total_ignores_the_page(api: Api) -> None:
    """Scenario: 모든 필터는 AND이고 total은 필터 적용 후 전체 건수이며 페이지와 무관하다."""
    # Given
    sap = await given_vendor(api, "SAP", ["ERP", "DB"])
    oracle = await given_vendor(api, "Oracle", ["ERP"])
    erp, db = sap.solutions["ERP"], sap.solutions["DB"]
    await given_logged_in_as(api, role="sales")
    hits = [
        await given_deal(
            api,
            vendor_id=sap.id,
            solution_id=erp,
            forecast_key="commit",
            revenue_date="2026-05-10",
            name=f"적중{n}",
        )
        for n in range(3)
    ]
    other = {"revenue_date": "2026-05-10", "forecast_key": "commit"}
    await given_deal(api, vendor_id=oracle.id, solution_id=oracle.solutions["ERP"], **other)
    await given_deal(api, vendor_id=sap.id, solution_id=db, **other)
    await given_deal(api, vendor_id=sap.id, solution_id=erp, **{**other, "forecast_key": "best"})
    await given_deal(
        api, vendor_id=sap.id, solution_id=erp, **{**other, "revenue_date": "2026-09-10"}
    )
    # When
    response = await when_list_deals(
        api,
        vendor_id=sap.id,
        solution_id=erp,
        forecast_key="commit",
        year=2026,
        quarter=2,
        offset=1,
        limit=1,
    )
    # Then
    then_status_is(response, 200)
    then_total_is(response, 3)
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["code"] in {h["code"] for h in hits}


async def test_month_filter_limits_expected_close(api: Api) -> None:
    """Scenario: year+month는 Expected Close가 그 달 1일~말일(양끝 포함)인 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    feb_first = await given_deal(api, revenue_date="2028-02-01")
    feb_last = await given_deal(api, revenue_date="2028-02-29")
    await given_deal(api, revenue_date="2028-01-31")
    await given_deal(api, revenue_date="2028-03-01")
    await given_deal(api, revenue_date="2027-02-15")
    # When
    response = await when_list_deals(api, year=2028, month=2)
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [feb_first["code"], feb_last["code"]])
    then_total_is(response, 2)


async def test_month_without_year_takes_this_year(api: Api) -> None:
    """Scenario: month만 주면 서버 업무 날짜의 올해 그 달로 좁힌다(분기와 같은 규칙)."""
    # Given
    this_year = api.clock.now().astimezone().year
    await given_logged_in_as(api, role="sales")
    hit = await given_deal(api, revenue_date=f"{this_year}-03-15")
    await given_deal(api, revenue_date=f"{this_year - 1}-03-15")
    await given_deal(api, revenue_date=f"{this_year}-04-15")
    # When
    response = await when_list_deals(api, month=3)
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [hit["code"]])


async def test_quarter_and_month_together_are_rejected(api: Api) -> None:
    """Scenario: quarter와 month를 함께 주면 422 invalid-value다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, year=2026, quarter=1, month=1)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


async def test_month_outside_one_to_twelve_is_rejected(api: Api) -> None:
    """Scenario: month가 1~12 밖이면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, year=2026, month=13)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
