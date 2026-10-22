"""Feature: 잘못된 Dashboard 요약 조회는 422(request-validation)로 거절한다.

year 누락·형식·범위, quarter 범위, 알 수 없는 파라미터(Dashboard에는 month가 없다)가 대상이다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.dashboard import when_get_dashboard_summary

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
        {"year": 2026, "quarter": "abc"},
        {"year": 2026, "month": 3},
        {"year": 2026, "vendor": "SAP"},
        {"year": 2026, "owner_user_id": "abc"},
        {"year": 2026, "vendor_id": "abc"},
    ],
    ids=[
        "no-year",
        "text-year",
        "year-low",
        "year-high",
        "quarter-0",
        "quarter-5",
        "text-quarter",
        "month-not-supported",
        "unknown-param",
        "text-owner",
        "text-vendor",
    ],
)
async def test_invalid_queries_are_rejected(api: Api, params: dict[str, str | int]) -> None:
    """Scenario: 형식·범위가 틀리거나 모르는 파라미터는 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_dashboard_summary(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
