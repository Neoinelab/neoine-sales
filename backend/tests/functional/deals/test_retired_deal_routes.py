"""Feature: 폐지된 Deal 경로는 더 이상 없다(404/405).

UUID 기반 경로, by-code, 단계 변경·단계 이력, 파이프라인 현황은 P1에서 폐지되었다(사용자 승인).
`/deals/{code}`는 형식이 틀린 값을 404로 처리하므로 UUID·pipeline도 404이고, PUT은 405다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.deals import given_deal

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

UUID = "6f1c1b3a-0000-4000-8000-000000000001"
RETIRED = [
    ("GET", f"/api/v1/deals/{UUID}"),
    ("PUT", f"/api/v1/deals/{UUID}"),
    ("DELETE", f"/api/v1/deals/{UUID}?confirm_code=x"),
    ("GET", "/api/v1/deals/by-code/20260101-AAAA"),
    ("POST", f"/api/v1/deals/{UUID}/stage"),
    ("GET", f"/api/v1/deals/{UUID}/stage-changes"),
    ("GET", "/api/v1/deals/pipeline"),
]


@pytest.mark.parametrize(("method", "path"), RETIRED, ids=[f"{m} {p}" for m, p in RETIRED])
async def test_a_retired_route_is_gone(api: Api, method: str, path: str) -> None:
    """Scenario: 폐지된 경로를 부르면 404 또는 405이다(본문이 있어도 마찬가지)."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await api.request(method, path, json={} if method in {"POST", "PUT"} else None)
    # Then
    assert response.status_code in {404, 405}, (response.status_code, response.text)


async def test_the_deal_stage_field_is_gone_from_the_responses(api: Api) -> None:
    """Scenario: Deal 응답에는 stage·id·code 구 필드가 없고 status_key/forecast_key를 쓴다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    deal = await given_deal(api)
    # Then
    for retired in (
        "stage",
        "id",
        "customer_id",
        "partner_id",
        "revenue_currency",
        "registered_by",
    ):
        assert retired not in deal, retired
    assert {"status_key", "forecast_key", "code"} <= set(deal)
