"""Feature: 영업은 목록을 정렬 기준과 방향을 골라 본다.

sort는 name·revenue_amount·revenue_date·last_updated_at·status, order는 asc·desc이고 기본은
last_updated_at 내림차순이다. 동률은 어느 정렬이든 code 오름차순이다. 화이트리스트 밖 값은 422다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deal_lists import then_codes_are
from tests.functional.steps.deals import given_deal, list_codes, when_list_deals

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

# (sort, 오름차순 결과의 Deal 번호). 3건의 키가 정렬마다 다른 순서가 되도록 만든 값이다.
ROWS = [
    ("charlie", 200, "2026-01-01", "price_negotiation"),  # 1
    ("alpha", 300, "2026-03-01", "introduction"),  # 2
    ("Bravo", 100, "2026-02-01", "prospecting"),  # 3
]
ASCENDING = [
    ("name", [2, 3, 1]),
    ("revenue_amount", [3, 1, 2]),
    ("revenue_date", [1, 3, 2]),
    ("last_updated_at", [1, 2, 3]),
    ("status", [3, 2, 1]),
]


async def _three_deals(api: Api) -> list[str]:
    codes = []
    for name, amount, day, status in ROWS:
        deal = await given_deal(
            api, name=name, revenue_amount=amount, revenue_date=day, status_key=status
        )
        codes.append(str(deal["code"]))
    return codes


@pytest.mark.parametrize(("sort", "numbers"), ASCENDING, ids=[s for s, _ in ASCENDING])
@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_each_sort_key_orders_ascending_and_descending(
    api: Api, sort: str, numbers: list[int], order: str
) -> None:
    """Scenario: 정렬 기준마다 오름차순·내림차순 결과가 기대한 순서다."""
    # Given
    await given_logged_in_as(api, role="sales")
    codes = await _three_deals(api)
    expected = [codes[n - 1] for n in numbers]
    # When
    response = await when_list_deals(api, sort=sort, order=order)
    # Then
    then_status_is(response, 200)
    then_codes_are(response, expected if order == "asc" else list(reversed(expected)))


async def test_the_default_is_the_most_recently_updated_first(api: Api) -> None:
    """Scenario: sort·order를 주지 않으면 최근 갱신 순(내림차순)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    codes = await _three_deals(api)
    # When
    response = await when_list_deals(api)
    # Then
    then_codes_are(response, list(reversed(codes)))


@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("sort", ["name", "revenue_amount", "revenue_date", "status"])
async def test_ties_are_ordered_by_code_ascending_in_both_directions(
    api: Api, sort: str, order: str
) -> None:
    """Scenario: 정렬 값이 같은 Deal은 오름차순·내림차순과 상관없이 code 오름차순이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deals = [await given_deal(api) for _ in range(4)]  # 값이 모두 같다
    # When
    response = await when_list_deals(api, sort=sort, order=order)
    # Then
    then_codes_are(response, sorted(str(d["code"]) for d in deals))


async def test_a_sorted_page_continues_where_the_previous_one_ended(api: Api) -> None:
    """Scenario: 정렬한 목록의 다음 페이지는 앞 페이지에 이어지고 total은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    codes = await _three_deals(api)
    expected = [codes[1], codes[2], codes[0]]  # name 오름차순
    # When
    first = await when_list_deals(api, sort="name", order="asc", offset=0, limit=2)
    second = await when_list_deals(api, sort="name", order="asc", offset=2, limit=2)
    # Then
    assert list_codes(first) + list_codes(second) == expected
    assert first.json()["total"] == second.json()["total"] == 3


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "revenueAmount"},
        {"sort": "stage"},
        {"sort": "name; drop table deals"},
        {"order": "up"},
        {"order": "DESC"},
    ],
)
async def test_a_sort_or_order_outside_the_whitelist_is_rejected(
    api: Api, params: dict[str, str]
) -> None:
    """Scenario: 화이트리스트 밖의 sort·order는 422이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, **params)
    # Then
    then_status_is(response, 422)
