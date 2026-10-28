"""Feature: Dashboard는 고른 Quarter만 집계하고, 그 숫자는 같은 조건의 Deal 목록과 일치한다.

`quarter`를 반복해 보내면 타일(Forecast)과 Status는 고른 분기의 Deal만 집계하고, 분기 행
`quarters`는 항상 Q1~Q4, `period.quarters`는 고른 분기다. 같은 분기 목록으로 Deal 목록을 조회한
total은 누른 숫자와 같다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.dashboard import (
    given_dashboard_deal,
    given_today_is,
    then_quarters_match_forecast_summary,
)
from tests.functional.steps.forecast import given_sales_user
from tests.functional.steps.forecast_keys import keys_by_outcome
from tests.functional.steps.quarters import when_get_dashboard_summary_of_quarters

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import Response

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _given_year_of_deals(api: Api) -> None:
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    for forecast, amount, day in (
        ("pipeline", 1, "2026-02-01"),
        ("commit", 2, "2026-05-01"),
        ("best", 4, "2026-08-01"),
        ("won", 8, "2026-11-01"),
        ("lost", 16, "2026-02-15"),
        ("pipeline", 32, "2025-08-01"),
    ):
        await given_dashboard_deal(api, owner=kim, forecast=forecast, amount=amount, day=day)


async def test_dashboard_tiles_of_several_quarters_sum_only_those_quarters(api: Api) -> None:
    """Scenario: Q1·Q3를 고르면 타일·Status는 두 분기의 Lost 제외 Deal만 집계한다."""
    # Given
    await _given_year_of_deals(api)
    # When
    response = await when_get_dashboard_summary_of_quarters(api, [1, 3], year=2026)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["period"]["quarters"] == [1, 3]
    assert body["period"]["quarter"] is None
    assert (
        body["forecasts"]["open_total"]["count"],
        body["forecasts"]["open_total"]["amount"],
    ) == (
        2,
        5,
    )
    assert (body["statuses"]["total"]["count"], body["statuses"]["total"]["amount"]) == (2, 5)
    assert [q["quarter"] for q in body["quarters"]] == [1, 2, 3, 4]


async def test_the_list_of_the_same_quarters_has_the_dashboard_totals(api: Api) -> None:
    """Scenario: 같은 분기 목록으로 Deal 목록을 조회한 total이 Open·Lost 제외 숫자와 같다."""
    # Given
    await _given_year_of_deals(api)
    summary = await when_get_dashboard_summary_of_quarters(api, [1, 3], year=2026)
    open_keys = keys_by_outcome(summary, {"open"})
    not_lost_keys = keys_by_outcome(summary, {"open", "won"})
    # When
    open_list = await _list(api, open_keys)
    not_lost_list = await _list(api, not_lost_keys)
    # Then
    body = summary.json()
    assert open_list.json()["total"] == body["forecasts"]["open_total"]["count"]
    assert not_lost_list.json()["total"] == body["statuses"]["total"]["count"]


async def _list(api: Api, keys: list[str]) -> Response:
    return await api.get(
        "/api/v1/deals",
        params={"year": 2026, "quarter": ["1", "3"], "forecast_key": keys, "limit": 200},
    )


async def test_quarter_rows_stay_the_four_quarters_when_several_are_chosen(api: Api) -> None:
    """Scenario: 분기를 골라도 quarters 행은 Q1~Q4이고 각 행은 그 분기 Forecast 요약과 같다."""
    # Given
    await _given_year_of_deals(api)
    # When
    response = await when_get_dashboard_summary_of_quarters(api, [1, 3], year=2026)
    # Then
    then_status_is(response, 200)
    await then_quarters_match_forecast_summary(api, response, year=2026)


async def test_all_four_quarters_read_like_no_quarter(api: Api) -> None:
    """Scenario: 네 분기를 모두 고르면 분기를 안 고른 것과 같은 period와 숫자다."""
    # Given
    await _given_year_of_deals(api)
    # When
    four = await when_get_dashboard_summary_of_quarters(api, [1, 2, 3, 4], year=2026)
    none = await when_get_dashboard_summary_of_quarters(api, [], year=2026)
    # Then
    then_status_is(four, 200)
    assert four.json()["period"] == none.json()["period"]
    assert four.json()["period"]["quarters"] == []
    assert four.json()["forecasts"] == none.json()["forecasts"]
    assert four.json()["statuses"] == none.json()["statuses"]


async def test_a_single_quarter_keeps_the_previous_period_shape(api: Api) -> None:
    """Scenario: 분기 하나면 period.quarter가 그 값이고 quarters는 [그 값]이다."""
    # Given
    await _given_year_of_deals(api)
    # When
    response = await when_get_dashboard_summary_of_quarters(api, [2], year=2026)
    # Then
    then_status_is(response, 200)
    assert response.json()["period"] == {
        "year": 2026,
        "quarter": 2,
        "quarters": [2],
        "from": "2026-04-01",
        "to": "2026-06-30",
    }


async def test_a_quarter_outside_one_to_four_is_rejected(api: Api) -> None:
    """Scenario: 1~4 밖의 분기가 있으면 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_dashboard_summary_of_quarters(api, [1, 0], year=2026)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
