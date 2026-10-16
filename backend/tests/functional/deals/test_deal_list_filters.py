"""Feature: 영업은 목록을 solution·forecast·연/분기·BANT Label로 좁혀 Deal을 찾는다.

연/분기는 Expected Close 기준이고 양끝을 포함한다(12-31은 Q4, 01-01은 Q1). 연/분기와 기간은
교집합이고, quarter는 연도와 함께만 쓸 수 있다. BANT Label은 구분별로 고르며 여러 구분은 AND다.
모든 필터는 서로 AND로 결합하고 total은 페이지와 무관하다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_lists import (
    QUARTER_WITHOUT_YEAR,
    then_codes_are,
    then_codes_are_exactly,
    then_total_is,
)
from tests.functional.steps.deals import (
    given_deal,
    given_label_id,
    when_list_deals,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_solution_and_forecast_filters_match_exactly(api: Api) -> None:
    """Scenario: solution은 정확히 같은 값, forecast는 같은 key인 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    erp = await given_deal(api, solution="S/4HANA", forecast_key="commit")
    await given_deal(api, solution="S/4HANA Cloud", forecast_key="commit")
    await given_deal(api, solution="S/4HANA", forecast_key="pipeline")
    # When
    response = await when_list_deals(api, solution="S/4HANA", forecast_key="commit")
    # Then
    then_status_is(response, 200)
    then_codes_are(response, [erp["code"]])
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


async def test_year_and_quarter_are_intersected_with_the_period(api: Api) -> None:
    """Scenario: 연/분기와 기간을 함께 주면 둘 다 만족하는 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    inside = await given_deal(api, revenue_date="2026-05-20")
    await given_deal(api, revenue_date="2026-04-10")
    await given_deal(api, revenue_date="2026-08-01")
    # When
    response = await when_list_deals(
        api, year=2026, quarter=2, revenue_from="2026-05-01", revenue_to="2026-05-31"
    )
    # Then
    then_codes_are(response, [inside["code"]])


async def test_a_quarter_without_a_year_is_rejected(api: Api) -> None:
    """Scenario: 연도 없이 quarter만 주면 422이고 도메인 문구가 나간다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, quarter=2)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == QUARTER_WITHOUT_YEAR


@pytest.mark.parametrize("params", [{"year": 2026, "quarter": 0}, {"year": 2026, "quarter": 5}])
async def test_a_quarter_outside_one_to_four_is_rejected(api: Api, params: dict[str, int]) -> None:
    """Scenario: quarter가 1~4 밖이면 422이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, **params)
    # Then
    then_status_is(response, 422)


async def test_bant_labels_of_one_and_several_categories(api: Api) -> None:
    """Scenario: BANT Label은 구분별로 고르고 여러 구분은 AND로 결합한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    full_budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    ceo = await given_label_id(api, category="authority", name="CEO 보고 완료")
    both = await given_deal(api, bant={"budget": full_budget, "authority": ceo})
    only_budget = await given_deal(api, bant={"budget": full_budget})
    await given_deal(api, bant={"authority": ceo})
    await given_deal(api)
    # When
    one = await when_list_deals(api, bant_budget=full_budget)
    several = await when_list_deals(api, bant_budget=full_budget, bant_authority=ceo)
    # Then
    then_codes_are_exactly(one, [both["code"], only_budget["code"]])
    then_codes_are(several, [both["code"]])
    then_total_is(several, 1)


async def test_an_unknown_bant_label_gives_an_empty_list_not_an_error(api: Api) -> None:
    """Scenario: 없는 Label id는 오류 없이 0건이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    # When
    response = await when_list_deals(api, bant_need=str(uuid4()))
    # Then
    then_status_is(response, 200)
    then_total_is(response, 0)


async def test_a_label_of_another_category_matches_nothing(api: Api) -> None:
    """Scenario: 예산 Label을 필요 구분 조건으로 주면 0건이다(오류 아님)."""
    # Given
    await given_logged_in_as(api, role="sales")
    full_budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    await given_deal(api, bant={"budget": full_budget})
    # When
    response = await when_list_deals(api, bant_need=full_budget)
    # Then
    then_status_is(response, 200)
    then_total_is(response, 0)


async def test_all_filters_are_combined_and_total_ignores_the_page(api: Api) -> None:
    """Scenario: 모든 필터는 AND이고 total은 필터 적용 후 전체 건수이며 페이지와 무관하다."""
    # Given
    await given_logged_in_as(api, role="sales")
    hits = [
        await given_deal(
            api,
            vendor="SAP",
            solution="ERP",
            forecast_key="commit",
            revenue_date="2026-05-10",
            name=f"적중{n}",
        )
        for n in range(3)
    ]
    await given_deal(
        api, vendor="Oracle", solution="ERP", forecast_key="commit", revenue_date="2026-05-10"
    )
    await given_deal(
        api, vendor="SAP", solution="DB", forecast_key="commit", revenue_date="2026-05-10"
    )
    await given_deal(
        api, vendor="SAP", solution="ERP", forecast_key="best", revenue_date="2026-05-10"
    )
    await given_deal(
        api, vendor="SAP", solution="ERP", forecast_key="commit", revenue_date="2026-09-10"
    )
    # When
    response = await when_list_deals(
        api,
        vendor="SAP",
        solution="ERP",
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
