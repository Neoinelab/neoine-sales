"""Feature: Forecast 요약은 로그인한 모든 역할이 읽고, 로그인하지 않으면 읽을 수 없다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.forecast import given_forecast_deal, given_sales_user, when_get_summary

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_can_read_summary(api: Api, role: str) -> None:
    """Scenario: admin·sales·user 모두 다른 담당자의 숫자까지 200으로 읽는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    kim = await given_sales_user(api, "kim")
    await given_forecast_deal(api, owner=kim, amount=7)
    await given_logged_in_as(api, role=role)  # type: ignore[arg-type]
    # When
    response = await when_get_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    assert response.json()["total"]["open_total"] == {"count": 1, "amount": 7}


async def test_anonymous_gets_401(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401(unauthenticated)이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_get_summary(api, year=2026)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
