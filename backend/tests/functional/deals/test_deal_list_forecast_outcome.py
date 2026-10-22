"""Feature: 영업은 목록을 Forecast 구분(Open·Won·Lost·Lost 제외)으로 좁혀 Deal을 찾는다.

구분은 Forecast 코드의 outcome 기준이라 admin이 추가한 Open 코드의 Deal도 Open에 들어간다.
`forecast_key`와는 AND로 결합하고, 파라미터가 없으면 지금과 같다(하위 호환). 모르는 값은
422(request-validation)다.
"""

from typing import TYPE_CHECKING, cast

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import given_code_created
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_lists import then_codes_are_exactly, then_total_is
from tests.functional.steps.deals import given_deal, given_sales_owner, when_list_deals

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _given_deals_of_every_outcome(api: Api) -> dict[str, str]:
    """admin 로그인 상태에서 forecast 구분별 Deal을 만든다. 구분 -> code."""
    owner = await given_sales_owner(api)
    codes: dict[str, str] = {}
    for forecast in ("pipeline", "commit", "won", "lost"):
        deal = await given_deal(
            api,
            owner_user_id=owner,
            forecast_key=forecast,
            status_key="contract_completed" if forecast == "won" else "prospecting",
            name=f"{forecast} deal",
        )
        codes[forecast] = str(deal["code"])
    return codes


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("open", ["pipeline", "commit"]),
        ("won", ["won"]),
        ("lost", ["lost"]),
        ("not_lost", ["pipeline", "commit", "won"]),
    ],
)
async def test_forecast_outcome_filter_selects_by_code_outcome(
    api: Api, outcome: str, expected: list[str]
) -> None:
    """Scenario: forecast_outcome은 Forecast 코드의 outcome이 같은 Deal만 돌려주고 total도 같다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_of_every_outcome(api)
    # When
    response = await when_list_deals(api, forecast_outcome=outcome)
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, sorted([codes[name] for name in expected]))
    then_total_is(response, len(expected))


async def test_forecast_outcome_open_includes_deals_of_a_code_added_by_admin(api: Api) -> None:
    """Scenario: admin이 추가한 Open 코드의 Deal도 open·not_lost에 들어가고 lost에는 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_of_every_outcome(api)
    added = await given_code_created(api, kind="forecast", name="Verbal")
    verbal = await given_deal(
        api,
        owner_user_id=await given_sales_owner(api),
        forecast_key=cast("str", added["key"]),
        name="verbal deal",
    )
    # When
    open_ = await when_list_deals(api, forecast_outcome="open")
    not_lost = await when_list_deals(api, forecast_outcome="not_lost")
    lost = await when_list_deals(api, forecast_outcome="lost")
    # Then
    then_codes_are_exactly(open_, sorted([codes["pipeline"], codes["commit"], str(verbal["code"])]))
    then_total_is(not_lost, 4)
    then_codes_are_exactly(lost, [codes["lost"]])


async def test_forecast_outcome_is_anded_with_forecast_key(api: Api) -> None:
    """Scenario: forecast_key와 함께 주면 둘 다 만족하는 Deal만 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    codes = await _given_deals_of_every_outcome(api)
    # When
    both = await when_list_deals(api, forecast_key="commit", forecast_outcome="open")
    conflicting = await when_list_deals(api, forecast_key="lost", forecast_outcome="not_lost")
    # Then
    then_codes_are_exactly(both, [codes["commit"]])
    then_total_is(conflicting, 0)


async def test_without_forecast_outcome_every_deal_is_listed(api: Api) -> None:
    """Scenario: forecast_outcome을 주지 않으면 지금처럼 모든 Deal이 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await _given_deals_of_every_outcome(api)
    # When
    response = await when_list_deals(api)
    # Then
    then_status_is(response, 200)
    then_total_is(response, 4)


@pytest.mark.parametrize("value", ["foo", "", "OPEN", "not-lost"])
async def test_unknown_forecast_outcome_is_rejected(api: Api, value: str) -> None:
    """Scenario: 모르는 forecast_outcome 값은 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, forecast_outcome=value)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
