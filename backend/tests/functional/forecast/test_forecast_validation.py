"""Feature: 잘못된 Forecast 요약 조회는 422로 거절한다.

형식·범위·알 수 없는 파라미터는 request-validation, Quarter와 월을 함께 고르면 invalid-value다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.forecast import when_get_summary

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"year": "abc"},
        {"year": 1899},
        {"year": 10000},
        {"year": 2026, "quarter": 0},
        {"year": 2026, "quarter": 5},
        {"year": 2026, "month": 0},
        {"year": 2026, "month": 13},
        {"year": 2026, "vendor": "SAP"},
        {"year": 2026, "owner_user_id": "abc"},
    ],
    ids=[
        "no-year",
        "text-year",
        "year-low",
        "year-high",
        "quarter-0",
        "quarter-5",
        "month-0",
        "month-13",
        "unknown-param",
        "text-owner",
    ],
)
async def test_invalid_queries_are_rejected(api: Api, params: dict[str, str | int]) -> None:
    """Scenario: 형식·범위가 틀리거나 모르는 파라미터는 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_summary(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_quarter_and_month_together_are_rejected(api: Api) -> None:
    """Scenario: Quarter와 월을 함께 주면 422 invalid-value와 안내 문구다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_summary(api, year=2026, quarter=1, month=1)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == "Quarter와 월은 함께 선택할 수 없습니다."
