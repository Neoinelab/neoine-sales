"""Feature: 영업은 Deal 목록을 여러 Forecast로 한꺼번에 좁혀 본다.

`forecast_key`를 반복해 보내면 그중 하나와 일치하는 Deal이 나오고(OR) total도 그 건수다. 단일 값
요청은 예전과 같고, 값이 50자를 넘거나 100개를 넘으면 422(request-validation)다. Dashboard의
Open·Lost 제외 숫자는 그 Forecast key 집합으로 센 목록 건수와 같다(admin이 추가한 Open 코드 포함).
"""

from datetime import date
from typing import TYPE_CHECKING, cast

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import given_code_created
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.dashboard import (
    given_dashboard_deal,
    given_today_is,
    when_get_dashboard_summary,
)
from tests.functional.steps.deal_lists import then_codes_are_exactly, then_total_is
from tests.functional.steps.deals import given_deal, given_sales_owner
from tests.functional.steps.forecast import given_sales_user
from tests.functional.steps.forecast_keys import keys_by_outcome, when_list_deals_of_forecasts

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _given_deals_of_forecasts(api: Api, *forecasts: str) -> dict[str, str]:
    """admin 로그인 상태에서 forecast마다 Deal 하나. forecast -> code."""
    owner = await given_sales_owner(api)
    codes: dict[str, str] = {}
    for forecast in forecasts:
        deal = await given_deal(
            api,
            owner_user_id=owner,
            forecast_key=forecast,
            status_key="contract_completed" if forecast == "won" else "prospecting",
            name=f"{forecast} deal",
        )
        codes[forecast] = str(deal["code"])
    return codes


async def test_list_deals_of_several_forecasts(api: Api) -> None:
    """Scenario: forecast_key를 두 번 보내면 둘 중 하나인 Deal만 나오고 total도 그 건수다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_of_forecasts(api, "pipeline", "best", "lost")
    # When
    response = await when_list_deals_of_forecasts(api, ["pipeline", "best"])
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["pipeline"], codes["best"]])
    then_total_is(response, 2)


async def test_a_single_forecast_key_still_works(api: Api) -> None:
    """Scenario: forecast_key 하나만 보내면 예전처럼 그 Forecast의 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_of_forecasts(api, "pipeline", "commit")
    # When
    response = await when_list_deals_of_forecasts(api, ["commit"])
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["commit"]])
    then_total_is(response, 1)


async def test_an_unknown_key_next_to_a_known_one_is_not_an_error(api: Api) -> None:
    """Scenario: 모르는 key는 오류가 아니고, 함께 준 key의 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_of_forecasts(api, "pipeline", "commit")
    # When
    response = await when_list_deals_of_forecasts(api, ["no_such", "commit"])
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["commit"]])


async def test_too_many_forecast_keys_are_rejected(api: Api) -> None:
    """Scenario: forecast_key가 101개이면 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals_of_forecasts(api, [f"k{i}" for i in range(101)])
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_a_forecast_key_longer_than_fifty_characters_is_rejected(api: Api) -> None:
    """Scenario: 50자를 넘는 key가 하나라도 있으면 422(request-validation)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals_of_forecasts(api, ["commit", "a" * 51])
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.fixture
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.mark.usefixtures("_seoul")
async def test_dashboard_open_total_equals_the_list_of_open_keys(api: Api) -> None:
    """Scenario: Open 합계와 Lost 제외 합계는 해당 key 집합으로 센 목록 total과 같다."""
    # Given
    await given_today_is(api, date(2026, 10, 23))
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    added = await given_code_created(api, kind="forecast", name="Verbal")
    verbal = cast("str", added["key"])
    for forecast, amount, day in (
        ("pipeline", 10, "2026-02-01"),
        ("commit", 20, "2026-05-01"),
        (verbal, 30, "2026-11-10"),
        ("won", 40, "2026-06-01"),
        ("lost", 50, "2026-07-01"),
    ):
        await given_dashboard_deal(api, owner=kim, forecast=forecast, amount=amount, day=day)
    # When
    summary = await when_get_dashboard_summary(api, year=2026)
    open_keys = keys_by_outcome(summary, {"open"})
    not_lost_keys = keys_by_outcome(summary, {"open", "won"})
    open_list = await when_list_deals_of_forecasts(api, open_keys, year=2026)
    not_lost_list = await when_list_deals_of_forecasts(api, not_lost_keys, year=2026)
    # Then
    body = summary.json()
    assert verbal in open_keys
    then_total_is(open_list, body["forecasts"]["open_total"]["count"])
    then_total_is(not_lost_list, body["statuses"]["total"]["count"])
    then_total_is(open_list, 3)
    then_total_is(not_lost_list, 4)
