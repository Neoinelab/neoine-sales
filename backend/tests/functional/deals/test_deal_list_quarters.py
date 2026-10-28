"""Feature: 영업은 Deal 목록을 여러 Quarter로 한꺼번에 좁혀 본다.

`quarter`를 반복해 보내면 그 분기 중 하나에 Expected Close가 속한 Deal만 나오고(OR) total도 그
건수다. 단일 값 요청은 예전과 같고, 1~4 밖의 값이거나 값이 4개를 넘으면 422(request-validation)다.
분기와 월을 함께 보내면 422(invalid-value)다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_lists import then_codes_are_exactly, then_total_is
from tests.functional.steps.deals import given_deal, given_sales_owner
from tests.functional.steps.quarters import when_list_deals_of_quarters

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _given_deals_on(api: Api, *days: str) -> dict[str, str]:
    """admin 로그인 상태에서 Expected Close마다 Deal 하나. 날짜 -> code."""
    owner = await given_sales_owner(api)
    codes: dict[str, str] = {}
    for day in days:
        deal = await given_deal(api, owner_user_id=owner, revenue_date=day, name=f"deal {day}")
        codes[day] = str(deal["code"])
    return codes


async def test_list_deals_of_several_quarters(api: Api) -> None:
    """Scenario: quarter를 두 번 보내면 두 분기의 Deal만(경계일 포함) 나오고 total도 그 건수다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_on(
        api,
        "2026-01-01",
        "2026-03-31",
        "2026-04-01",
        "2026-06-30",
        "2026-07-01",
        "2026-09-30",
        "2026-10-01",
        "2025-08-01",
    )
    # When
    response = await when_list_deals_of_quarters(api, [1, 3], year=2026)
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(
        response, [codes[d] for d in ("2026-01-01", "2026-03-31", "2026-07-01", "2026-09-30")]
    )
    then_total_is(response, 4)


async def test_a_single_quarter_still_works(api: Api) -> None:
    """Scenario: quarter 하나만 보내면 예전처럼 그 분기의 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_on(api, "2026-04-01", "2026-06-30", "2026-07-01")
    # When
    response = await when_list_deals_of_quarters(api, [2], year=2026)
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["2026-04-01"], codes["2026-06-30"]])
    then_total_is(response, 2)


async def test_all_four_quarters_list_the_whole_year(api: Api) -> None:
    """Scenario: 네 분기를 모두 보내면 분기 조건이 없는 것과 같다(그 해 전체)."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_on(api, "2025-12-31", "2026-01-01", "2026-12-31", "2027-01-01")
    # When
    response = await when_list_deals_of_quarters(api, [4, 3, 2, 1], year=2026)
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["2026-01-01"], codes["2026-12-31"]])


async def test_a_quarter_outside_one_to_four_is_rejected(api: Api) -> None:
    """Scenario: 1~4 밖의 분기가 하나라도 있으면 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals_of_quarters(api, [1, 5], year=2026)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_more_than_four_quarter_values_are_rejected(api: Api) -> None:
    """Scenario: quarter 값이 5개이면 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals_of_quarters(api, [1, 2, 3, 4, 1], year=2026)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_quarters_together_with_a_month_are_rejected(api: Api) -> None:
    """Scenario: 분기와 월을 함께 보내면 422(invalid-value)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals_of_quarters(api, [1, 3], year=2026, month=2)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
