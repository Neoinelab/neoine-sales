"""Feature: 영업은 목록을 담당자·고객사·파트너사·Vendor·Forecast 열 기준으로 정렬해 본다.

sort에 owner·customer·partner·vendor·forecast를 더 줄 수 있다. 담당자·고객·파트너·Vendor는 이름의
소문자 순, Forecast는 코드의 현재 순서다. 파트너·Vendor가 없는 Deal은 오름차순·내림차순 모두
맨 뒤에 둔다. 동률은 Deal code 오름차순이다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deal_list_sort import (
    ASCENDING_NUMBERS,
    given_three_deals_with_different_columns,
    given_two_deals_without_partner_or_vendor,
)
from tests.functional.steps.deal_lists import then_codes_are
from tests.functional.steps.deals import when_list_deals

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("sort", "numbers"), ASCENDING_NUMBERS.items(), ids=list(ASCENDING_NUMBERS)
)
@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_sorting_the_list_by_each_column(
    api: Api, sort: str, numbers: list[int], order: str
) -> None:
    """Scenario: 새 정렬 기준마다 오름차순·내림차순 결과가 기대한 순서다."""
    # Given
    codes = await given_three_deals_with_different_columns(api)
    await given_logged_in_as(api, role="sales")
    expected = [codes[n - 1] for n in numbers]
    # When
    response = await when_list_deals(api, sort=sort, order=order)
    # Then
    then_status_is(response, 200)
    then_codes_are(response, expected if order == "asc" else list(reversed(expected)))


@pytest.mark.parametrize("sort", ["partner", "vendor"])
@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_deals_without_partner_or_vendor_are_listed_last(
    api: Api, sort: str, order: str
) -> None:
    """Scenario: 파트너·Vendor가 없는 Deal은 어느 방향이든 맨 뒤이고 그들끼리는 code 순이다."""
    # Given
    codes = await given_two_deals_without_partner_or_vendor(api)
    await given_logged_in_as(api, role="sales")
    with_value = [codes[2], codes[0]]  # 소문자 기준 alpha(3번), bravo(1번)
    expected = (with_value if order == "asc" else list(reversed(with_value))) + [codes[1], codes[3]]
    # When
    response = await when_list_deals(api, sort=sort, order=order)
    # Then
    then_status_is(response, 200)
    then_codes_are(response, expected)


async def test_a_page_continues_the_sorted_order(api: Api) -> None:
    """Scenario: 새 정렬 기준에서 2페이지는 1페이지 다음 순서다."""
    # Given
    codes = await given_three_deals_with_different_columns(api)
    await given_logged_in_as(api, role="sales")
    ascending = [codes[n - 1] for n in ASCENDING_NUMBERS["owner"]]
    # When
    response = await when_list_deals(api, sort="owner", order="asc", offset=2, limit=2)
    # Then
    then_status_is(response, 200)
    then_codes_are(response, ascending[2:])
